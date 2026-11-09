import asyncio
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from io import BytesIO
from uuid import UUID

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet
from sqlalchemy import Date, Interval, and_, cast, func, literal, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.core.config import Settings
from app.core.logging import get_logger
from app.domains.canje.models import Canje
from app.domains.negocio.models import Negocio
from app.domains.operacion.models import Operacion
from app.domains.reportes.schemas import (
    ReporteDia,
    ReportePuntosData,
    ReportePuntosQuery,
    ReporteSucursal,
    ReporteTotales,
    ReporteUsuario,
)
from app.domains.sucursal.models import Sucursal
from app.domains.users.models import User
from app.shared.enums import EstadoCanje, Role, TipoNegocio, TipoReportePuntos


logger = get_logger(__name__)


@dataclass(frozen=True)
class _FuenteReporte:
    """Columnas de la tabla origen que alimentan el reporte."""

    fecha: ColumnElement
    sucursal_id: ColumnElement
    actor_id: ColumnElement
    puntos: ColumnElement
    bs: ColumnElement
    filtros: tuple[ColumnElement[bool], ...]


class ReporteService:
    """Consultas y generación de reportes."""

    _ROLES_ELEGIBLES: dict[TipoReportePuntos, frozenset[Role]] = {
        TipoReportePuntos.ASIGNADOS: frozenset({Role.ADMIN, Role.CAJERO}),
        TipoReportePuntos.CANJEADOS: frozenset({Role.ADMIN, Role.CAJERO, Role.SOCIO}),
    }
    _TIPOS_NEGOCIO: dict[TipoReportePuntos, frozenset[TipoNegocio]] = {
        TipoReportePuntos.ASIGNADOS: frozenset({TipoNegocio.MAIN}),
        TipoReportePuntos.CANJEADOS: frozenset({TipoNegocio.MAIN, TipoNegocio.SOCIO}),
    }
    _ORDEN_TIPO_NEGOCIO = {TipoNegocio.MAIN: 0, TipoNegocio.SOCIO: 1}

    XLSX_MEDIA_TYPE = (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    # ------------------------------------------------------------------
    # Consultas
    # ------------------------------------------------------------------

    @staticmethod
    def _fuente(tipo: TipoReportePuntos) -> _FuenteReporte:
        if tipo is TipoReportePuntos.ASIGNADOS:
            return _FuenteReporte(
                fecha=Operacion.created_at,
                sucursal_id=Operacion.sucursal_id,
                actor_id=Operacion.emisor_id,
                puntos=Operacion.total_puntos,
                bs=Operacion.total_compra,
                filtros=(Operacion.is_deleted.is_(False),),
            )
        # Un canje en estado final no puede modificarse (trigger
        # trg_canje_estado_final_inmutable), por lo que updated_at es la
        # fecha efectiva en que se confirmó el canje.
        return _FuenteReporte(
            fecha=Canje.updated_at,
            sucursal_id=Canje.sucursal_id,
            actor_id=Canje.dador_id,
            puntos=Canje.total_puntos,
            bs=Canje.total_costo,
            filtros=(
                Canje.is_deleted.is_(False),
                Canje.status == EstadoCanje.CANJEADO,
            ),
        )

    @staticmethod
    def _rango_utc(
        query: ReportePuntosQuery,
        offset_hours: int,
    ) -> tuple[datetime, datetime]:
        zona = timezone(timedelta(hours=offset_hours))
        inicio = datetime.combine(query.fecha_inicio, time.min, tzinfo=zona)
        fin = datetime.combine(
            query.fecha_fin + timedelta(days=1),
            time.min,
            tzinfo=zona,
        )
        return inicio, fin

    @staticmethod
    def _dia_local(columna: ColumnElement, offset_hours: int) -> ColumnElement:
        return cast(
            func.timezone("UTC", columna)
            + literal(timedelta(hours=offset_hours), Interval()),
            Date,
        )

    @staticmethod
    def _totales(cantidad: object, puntos: object, bs: object) -> ReporteTotales:
        return ReporteTotales(
            cantidad=int(cantidad or 0),
            puntos=int(puntos or 0),
            bs=Decimal(bs or 0).quantize(Decimal("0.01")),
        )

    @staticmethod
    def _sumar(destino: ReporteTotales, origen: ReporteTotales) -> None:
        destino.cantidad += origen.cantidad
        destino.puntos += origen.puntos
        destino.bs += origen.bs

    @classmethod
    async def _por_dia_y_sucursal(
        cls,
        db_session: AsyncSession,
        fuente: _FuenteReporte,
        periodo: tuple[datetime, datetime],
        offset_hours: int,
    ) -> dict[tuple[date, UUID], ReporteTotales]:
        dia = cls._dia_local(fuente.fecha, offset_hours).label("dia")
        result = await db_session.execute(
            select(
                dia,
                fuente.sucursal_id,
                func.count(),
                func.sum(fuente.puntos),
                func.sum(fuente.bs),
            )
            .where(
                *fuente.filtros,
                fuente.fecha >= periodo[0],
                fuente.fecha < periodo[1],
            )
            .group_by(dia, fuente.sucursal_id)
        )
        return {
            (row[0], row[1]): cls._totales(row[2], row[3], row[4])
            for row in result.all()
        }

    @classmethod
    async def _por_actor(
        cls,
        db_session: AsyncSession,
        fuente: _FuenteReporte,
        periodo: tuple[datetime, datetime],
    ) -> dict[UUID, ReporteTotales]:
        result = await db_session.execute(
            select(
                fuente.actor_id,
                func.count(),
                func.sum(fuente.puntos),
                func.sum(fuente.bs),
            )
            .where(
                *fuente.filtros,
                fuente.fecha >= periodo[0],
                fuente.fecha < periodo[1],
            )
            .group_by(fuente.actor_id)
        )
        return {
            row[0]: cls._totales(row[1], row[2], row[3]) for row in result.all()
        }

    @classmethod
    async def _sucursales(
        cls,
        db_session: AsyncSession,
        tipo: TipoReportePuntos,
        ids_con_datos: Iterable[UUID],
    ) -> list[ReporteSucursal]:
        # Activas del tipo de negocio que corresponde, más cualquier sucursal
        # (aunque esté eliminada) que tenga datos en el periodo, para que el
        # total del sistema sea siempre la suma de las columnas visibles.
        condiciones: list[ColumnElement[bool]] = [
            and_(
                Sucursal.is_deleted.is_(False),
                Negocio.is_deleted.is_(False),
                Negocio.tipo.in_(cls._TIPOS_NEGOCIO[tipo]),
            )
        ]
        ids = list(ids_con_datos)
        if ids:
            condiciones.append(Sucursal.id.in_(ids))

        result = await db_session.execute(
            select(Sucursal, Negocio)
            .join(Negocio, Negocio.id == Sucursal.negocio_id)
            .where(or_(*condiciones))
        )
        filas = sorted(
            result.all(),
            key=lambda row: (
                cls._ORDEN_TIPO_NEGOCIO.get(row[1].tipo, 99),
                row[1].nombre.casefold(),
                row[0].nombre.casefold(),
                str(row[0].id),
            ),
        )
        return [
            ReporteSucursal(
                id=sucursal.id,
                nombre=sucursal.nombre,
                negocio_nombre=negocio.nombre,
                eliminada=sucursal.is_deleted or negocio.is_deleted,
            )
            for sucursal, negocio in filas
        ]

    @classmethod
    async def _usuarios(
        cls,
        db_session: AsyncSession,
        tipo: TipoReportePuntos,
        totales_por_actor: dict[UUID, ReporteTotales],
    ) -> list[ReporteUsuario]:
        # Activos que pueden realizar la acción (aunque tengan cero) y
        # cualquier usuario que la haya realizado en el periodo, sin importar
        # su rol actual ni si fue eliminado.
        condiciones: list[ColumnElement[bool]] = [
            and_(
                User.is_deleted.is_(False),
                User.role.in_(cls._ROLES_ELEGIBLES[tipo]),
            )
        ]
        if totales_por_actor:
            condiciones.append(User.id.in_(list(totales_por_actor)))

        result = await db_session.execute(select(User).where(or_(*condiciones)))
        usuarios = [
            ReporteUsuario(
                id=user.id,
                nombre=" ".join(
                    part for part in (user.nombre, user.apellidos) if part
                ),
                ci=user.ci,
                role=user.role,
                eliminado=user.is_deleted,
                totales=totales_por_actor.get(user.id, ReporteTotales()),
            )
            for user in result.scalars().all()
        ]
        usuarios.sort(
            key=lambda u: (
                -u.totales.bs,
                -u.totales.puntos,
                u.nombre.casefold(),
                u.ci,
            )
        )
        return usuarios

    @classmethod
    async def get_puntos(
        cls,
        db_session: AsyncSession,
        query: ReportePuntosQuery,
        settings: Settings,
    ) -> ReportePuntosData:
        offset_hours = settings.TIMEZONE_OFFSET_HOURS
        fuente = cls._fuente(query.tipo)
        periodo = cls._rango_utc(query, offset_hours)

        por_dia_sucursal = await cls._por_dia_y_sucursal(
            db_session,
            fuente,
            periodo,
            offset_hours,
        )
        por_actor = await cls._por_actor(db_session, fuente, periodo)
        sucursales = await cls._sucursales(
            db_session,
            query.tipo,
            {sucursal_id for _, sucursal_id in por_dia_sucursal},
        )
        usuarios = await cls._usuarios(db_session, query.tipo, por_actor)

        total_por_sucursal = {s.id: ReporteTotales() for s in sucursales}
        total = ReporteTotales()
        dias: list[ReporteDia] = []
        dias_periodo = (query.fecha_fin - query.fecha_inicio).days + 1
        for offset in range(dias_periodo):
            dia = query.fecha_inicio + timedelta(days=offset)
            por_sucursal: dict[UUID, ReporteTotales] = {}
            total_dia = ReporteTotales()
            for sucursal in sucursales:
                valores = por_dia_sucursal.get((dia, sucursal.id), ReporteTotales())
                por_sucursal[sucursal.id] = valores
                cls._sumar(total_dia, valores)
                cls._sumar(total_por_sucursal[sucursal.id], valores)
            cls._sumar(total, total_dia)
            dias.append(ReporteDia(dia=dia, por_sucursal=por_sucursal, total=total_dia))

        return ReportePuntosData(
            query=query,
            sucursales=sucursales,
            dias=dias,
            total_por_sucursal=total_por_sucursal,
            total=total,
            usuarios=usuarios,
        )

    # ------------------------------------------------------------------
    # Excel
    # ------------------------------------------------------------------

    _FORMATO_FECHA = "DD/MM/YYYY"
    _FORMATO_ENTERO = "#,##0"
    _FORMATO_BS = "#,##0.00"
    _FUENTE_TITULO = Font(bold=True, size=13)
    _FUENTE_NEGRITA = Font(bold=True)
    _RELLENO_ENCABEZADO = PatternFill("solid", fgColor="DDE4EE")
    _RELLENO_TOTAL = PatternFill("solid", fgColor="EEF1F5")
    _BORDE = Border(
        left=Side(style="thin", color="B7C0CC"),
        right=Side(style="thin", color="B7C0CC"),
        top=Side(style="thin", color="B7C0CC"),
        bottom=Side(style="thin", color="B7C0CC"),
    )
    _CENTRADO = Alignment(horizontal="center", vertical="center", wrap_text=True)

    @staticmethod
    def _etiqueta_tipo(tipo: TipoReportePuntos) -> str:
        return "asignados" if tipo is TipoReportePuntos.ASIGNADOS else "canjeados"

    @staticmethod
    def _etiqueta_bs(tipo: TipoReportePuntos) -> str:
        return "Bs compra" if tipo is TipoReportePuntos.ASIGNADOS else "Bs vale"

    @classmethod
    def nombre_archivo(cls, query: ReportePuntosQuery) -> str:
        return (
            f"reporte_puntos_{cls._etiqueta_tipo(query.tipo)}_"
            f"{query.fecha_inicio.isoformat()}_{query.fecha_fin.isoformat()}.xlsx"
        )

    @classmethod
    def _titulo(cls, ws: Worksheet, data: ReportePuntosData, subtitulo: str) -> None:
        query = data.query
        ws["A1"] = (
            f"Reporte de puntos {cls._etiqueta_tipo(query.tipo)} {subtitulo} "
            f"del {query.fecha_inicio:%d/%m/%Y} al {query.fecha_fin:%d/%m/%Y}"
        )
        ws["A1"].font = cls._FUENTE_TITULO

    @classmethod
    def _encabezado(cls, ws: Worksheet, row: int, column: int, value: str) -> None:
        cell = ws.cell(row=row, column=column, value=value)
        cell.font = cls._FUENTE_NEGRITA
        cell.fill = cls._RELLENO_ENCABEZADO
        cell.alignment = cls._CENTRADO
        cell.border = cls._BORDE

    @classmethod
    def _escribir_totales(
        cls,
        ws: Worksheet,
        row: int,
        column: int,
        totales: ReporteTotales,
        es_total: bool = False,
    ) -> None:
        valores = (
            (totales.cantidad, cls._FORMATO_ENTERO),
            (totales.puntos, cls._FORMATO_ENTERO),
            (totales.bs, cls._FORMATO_BS),
        )
        for index, (value, number_format) in enumerate(valores):
            cell = ws.cell(row=row, column=column + index, value=value)
            cell.number_format = number_format
            cell.border = cls._BORDE
            if es_total:
                cell.font = cls._FUENTE_NEGRITA
                cell.fill = cls._RELLENO_TOTAL

    @classmethod
    def _hoja_sucursales(cls, ws: Worksheet, data: ReportePuntosData) -> None:
        ws.title = "Por sucursal"
        cls._titulo(ws, data, "por sucursal")
        etiqueta_bs = cls._etiqueta_bs(data.query.tipo)

        cls._encabezado(ws, 3, 1, "Día")
        cls._encabezado(ws, 4, 1, "")
        ws.merge_cells(start_row=3, start_column=1, end_row=4, end_column=1)

        grupos = [
            (
                f"{s.negocio_nombre} · {s.nombre}"
                + (" (eliminada)" if s.eliminada else "")
            )
            for s in data.sucursales
        ]
        grupos.append("TOTAL SISTEMA")
        for index, titulo in enumerate(grupos):
            column = 2 + index * 3
            for offset in range(3):
                cls._encabezado(ws, 3, column + offset, titulo if offset == 0 else "")
            ws.merge_cells(
                start_row=3,
                start_column=column,
                end_row=3,
                end_column=column + 2,
            )
            for offset, subtitulo in enumerate(("Cantidad", "Puntos", etiqueta_bs)):
                cls._encabezado(ws, 4, column + offset, subtitulo)

        row = 5
        for dia in data.dias:
            cell = ws.cell(row=row, column=1, value=dia.dia)
            cell.number_format = cls._FORMATO_FECHA
            cell.border = cls._BORDE
            for index, sucursal in enumerate(data.sucursales):
                cls._escribir_totales(ws, row, 2 + index * 3, dia.por_sucursal[sucursal.id])
            cls._escribir_totales(ws, row, 2 + len(data.sucursales) * 3, dia.total)
            row += 1

        cell = ws.cell(row=row, column=1, value="TOTAL")
        cell.font = cls._FUENTE_NEGRITA
        cell.fill = cls._RELLENO_TOTAL
        cell.border = cls._BORDE
        for index, sucursal in enumerate(data.sucursales):
            cls._escribir_totales(
                ws,
                row,
                2 + index * 3,
                data.total_por_sucursal[sucursal.id],
                es_total=True,
            )
        cls._escribir_totales(
            ws,
            row,
            2 + len(data.sucursales) * 3,
            data.total,
            es_total=True,
        )

        ws.column_dimensions["A"].width = 13
        for column in range(2, 2 + len(grupos) * 3):
            ws.column_dimensions[get_column_letter(column)].width = 13
        ws.row_dimensions[3].height = 32
        ws.freeze_panes = "B5"

    @classmethod
    def _hoja_usuarios(cls, ws: Worksheet, data: ReportePuntosData) -> None:
        ws.title = "Por usuario"
        cls._titulo(ws, data, "por usuario")

        encabezados = (
            "Usuario",
            "CI",
            "Rol actual",
            "Cantidad",
            "Puntos",
            cls._etiqueta_bs(data.query.tipo),
        )
        for index, titulo in enumerate(encabezados, start=1):
            cls._encabezado(ws, 3, index, titulo)

        row = 4
        total = ReporteTotales()
        for usuario in data.usuarios:
            nombre = usuario.nombre + (" (eliminado)" if usuario.eliminado else "")
            for column, value in enumerate(
                (nombre, usuario.ci, usuario.role.value),
                start=1,
            ):
                ws.cell(row=row, column=column, value=value).border = cls._BORDE
            cls._escribir_totales(ws, row, 4, usuario.totales)
            cls._sumar(total, usuario.totales)
            row += 1

        for column in range(1, 4):
            cell = ws.cell(row=row, column=column, value="TOTAL" if column == 1 else "")
            cell.font = cls._FUENTE_NEGRITA
            cell.fill = cls._RELLENO_TOTAL
            cell.border = cls._BORDE
        cls._escribir_totales(ws, row, 4, total, es_total=True)

        for column, width in zip("ABCDEF", (36, 14, 13, 12, 12, 14)):
            ws.column_dimensions[column].width = width
        ws.freeze_panes = "A4"

    @classmethod
    def generar_excel(cls, data: ReportePuntosData) -> bytes:
        workbook = Workbook()
        cls._hoja_sucursales(workbook.active, data)
        cls._hoja_usuarios(workbook.create_sheet(), data)

        buffer = BytesIO()
        workbook.save(buffer)
        return buffer.getvalue()

    @classmethod
    async def generar_excel_puntos(
        cls,
        db_session: AsyncSession,
        query: ReportePuntosQuery,
        settings: Settings,
    ) -> bytes:
        data = await cls.get_puntos(db_session, query, settings)
        content = await asyncio.to_thread(cls.generar_excel, data)
        logger.info(
            "Reporte de puntos generado: tipo=%s inicio=%s fin=%s sucursales=%s usuarios=%s",
            query.tipo.value,
            query.fecha_inicio,
            query.fecha_fin,
            len(data.sucursales),
            len(data.usuarios),
        )
        return content
