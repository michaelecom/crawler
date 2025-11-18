"""
GraphML Exporter для экспорта графа ссылок в GraphML формат.

GraphML - это XML формат для представления графов,
который поддерживается инструментами вроде:
- Gephi
- Cytoscape
- yEd
- NetworkX

Поддерживает:
- Экспорт directed/undirected графов
- Атрибуты узлов (URL metadata)
- Атрибуты рёбер (link metadata)
- Фильтрация по количеству узлов
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Set
import xml.etree.ElementTree as ET
from xml.dom import minidom

from webcrawler.export.base import BaseExporter
from webcrawler.storage.database import DatabaseManager


class GraphMLExporter(BaseExporter):
    """
    Экспортер графа ссылок в GraphML формат.

    Создаёт граф где:
    - Узлы = URL
    - Рёбра = ссылки между URL

    Example:
        >>> exporter = GraphMLExporter(db_manager)
        >>> await exporter.export(
        ...     session_id="abc123",
        ...     output_path="graph.graphml",
        ...     max_nodes=1000,
        ...     include_external=False
        ... )
    """

    async def export(
        self,
        session_id: str,
        output_path: str,
        max_nodes: Optional[int] = None,
        include_external: bool = True,
        node_attributes: Optional[List[str]] = None,
        edge_attributes: Optional[List[str]] = None,
        **options
    ) -> None:
        """
        Экспортировать граф в GraphML.

        Args:
            session_id: ID сессии для экспорта
            output_path: Путь к выходному GraphML файлу
            max_nodes: Максимальное количество узлов (для ограничения)
            include_external: Включать внешние ссылки
            node_attributes: Список атрибутов узлов для включения
            edge_attributes: Список атрибутов рёбер для включения
            **options: Дополнительные опции

        Raises:
            ValueError: Если сессия не найдена
        """
        self.logger.info(f"Starting GraphML export for session {session_id}")

        # Получить данные
        data = await self._fetch_session_data(session_id)

        # Дефолтные атрибуты
        if node_attributes is None:
            node_attributes = [
                "url", "status_code", "depth", "size_bytes",
                "response_time", "title"
            ]

        if edge_attributes is None:
            edge_attributes = ["link_type", "anchor_text", "rel"]

        # Подготовить путь
        output = self._prepare_output_path(output_path)

        # Построить граф
        graphml = self._build_graphml(
            data,
            max_nodes,
            include_external,
            node_attributes,
            edge_attributes
        )

        # Записать в файл с pretty print
        xml_str = minidom.parseString(
            ET.tostring(graphml, encoding="utf-8")
        ).toprettyxml(indent="  ")

        with open(output, "w", encoding="utf-8") as f:
            f.write(xml_str)

        self.logger.info(f"GraphML exported to {output}")

    def _build_graphml(
        self,
        data: Dict[str, Any],
        max_nodes: Optional[int],
        include_external: bool,
        node_attrs: List[str],
        edge_attrs: List[str]
    ) -> ET.Element:
        """
        Построить GraphML структуру.

        Args:
            data: Данные сессии
            max_nodes: Максимум узлов
            include_external: Включать внешние ссылки
            node_attrs: Атрибуты узлов
            edge_attrs: Атрибуты рёбер

        Returns:
            ET.Element с GraphML структурой
        """
        urls = data["urls"]
        links = data["links"]

        # Ограничить количество узлов
        if max_nodes and len(urls) > max_nodes:
            urls = urls[:max_nodes]
            self.logger.warning(
                f"Limited to {max_nodes} nodes (total: {len(data['urls'])})"
            )

        # Создать множество ID узлов
        node_ids = {url.url for url in urls}

        # Фильтровать ссылки
        filtered_links = []
        for link in links:
            # Проверка что source и target существуют
            if link.source_url not in node_ids:
                continue

            if not include_external and link.link_type == "external":
                continue

            if link.target_url not in node_ids and not include_external:
                continue

            filtered_links.append(link)

        self.logger.info(
            f"Building graph: {len(urls)} nodes, {len(filtered_links)} edges"
        )

        # Создать GraphML root
        graphml = ET.Element("graphml", {
            "xmlns": "http://graphml.graphdrawing.org/xmlns",
            "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
            "xsi:schemaLocation": "http://graphml.graphdrawing.org/xmlns "
                                 "http://graphml.graphdrawing.org/xmlns/1.0/graphml.xsd"
        })

        # Определить ключи для атрибутов узлов
        for attr in node_attrs:
            key = ET.SubElement(graphml, "key", {
                "id": f"node_{attr}",
                "for": "node",
                "attr.name": attr,
                "attr.type": self._get_attr_type(attr)
            })

        # Определить ключи для атрибутов рёбер
        for attr in edge_attrs:
            key = ET.SubElement(graphml, "key", {
                "id": f"edge_{attr}",
                "for": "edge",
                "attr.name": attr,
                "attr.type": "string"
            })

        # Создать граф
        graph = ET.SubElement(graphml, "graph", {
            "id": "CrawlGraph",
            "edgedefault": "directed"
        })

        # Добавить узлы
        url_to_id = {}
        for i, url in enumerate(urls):
            node_id = f"n{i}"
            url_to_id[url.url] = node_id

            node = ET.SubElement(graph, "node", {"id": node_id})

            # Добавить атрибуты узла
            for attr in node_attrs:
                value = self._get_node_attr_value(url, attr)
                if value is not None:
                    data_elem = ET.SubElement(node, "data", {
                        "key": f"node_{attr}"
                    })
                    data_elem.text = str(value)

        # Добавить рёбра
        edge_count = 0
        for link in filtered_links:
            source_id = url_to_id.get(link.source_url)
            target_id = url_to_id.get(link.target_url)

            # Если target внешний и include_external=True
            if target_id is None and include_external:
                # Создать узел для внешнего URL
                target_id = f"n_ext_{edge_count}"
                url_to_id[link.target_url] = target_id

                ext_node = ET.SubElement(graph, "node", {"id": target_id})
                data_elem = ET.SubElement(ext_node, "data", {
                    "key": "node_url"
                })
                data_elem.text = link.target_url

            if source_id is None or target_id is None:
                continue

            edge = ET.SubElement(graph, "edge", {
                "id": f"e{edge_count}",
                "source": source_id,
                "target": target_id
            })

            # Добавить атрибуты ребра
            for attr in edge_attrs:
                value = self._get_edge_attr_value(link, attr)
                if value is not None:
                    data_elem = ET.SubElement(edge, "data", {
                        "key": f"edge_{attr}"
                    })
                    data_elem.text = str(value)

            edge_count += 1

        return graphml

    def _get_attr_type(self, attr_name: str) -> str:
        """
        Определить тип атрибута для GraphML.

        Args:
            attr_name: Имя атрибута

        Returns:
            Тип атрибута (int, double, string, boolean)
        """
        int_attrs = ["status_code", "depth", "size_bytes", "internal_links_count", "external_links_count"]
        float_attrs = ["response_time"]
        bool_attrs = ["has_forms", "has_schema_org", "nofollow"]

        if attr_name in int_attrs:
            return "int"
        elif attr_name in float_attrs:
            return "double"
        elif attr_name in bool_attrs:
            return "boolean"
        else:
            return "string"

    def _get_node_attr_value(self, url: Any, attr: str) -> Optional[Any]:
        """
        Получить значение атрибута узла.

        Args:
            url: URL объект
            attr: Имя атрибута

        Returns:
            Значение атрибута или None
        """
        value = getattr(url, attr, None)

        # Специальная обработка для некоторых типов
        if value is None:
            return None

        if attr == "title" and value:
            # Экранировать XML
            return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        return value

    def _get_edge_attr_value(self, link: Any, attr: str) -> Optional[Any]:
        """
        Получить значение атрибута ребра.

        Args:
            link: Link объект
            attr: Имя атрибута

        Returns:
            Значение атрибута или None
        """
        value = getattr(link, attr, None)

        if value is None:
            return None

        if isinstance(value, str):
            # Экранировать XML
            return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        return value
