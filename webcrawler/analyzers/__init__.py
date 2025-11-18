"""
Analyzers <>4C;L 4;O 0=0;870 :>=B5=B0 8 40==KE :@0C;8=30.

:;NG05B:
- RobotsParser: ?0@A8=3 robots.txt
- SitemapParser: ?0@A8=3 sitemap.xml
- ContentAnalyzer: SEO 8 content 0=0;87
- LinkExtractor: ?@>428=CBK9 0=0;87 AAK;>:
- StatsCalculator: 03@538@>20==0O AB0B8AB8:0

A?>;L7>20=85:
    >>> from webcrawler.analyzers import ContentAnalyzer
    >>> from webcrawler.storage.database import DatabaseManager
    >>>
    >>> db = DatabaseManager(config)
    >>> await db.initialize()
    >>>
    >>> # Content 0=0;87
    >>> analyzer = ContentAnalyzer(db)
    >>> report = await analyzer.analyze(session_id="abc123")
    >>> print(f"SEO Score: {report.seo_score}")
    >>>
    >>> # Link 0=0;87
    >>> extractor = LinkExtractor(db)
    >>> link_report = await extractor.analyze(session_id="abc123")
    >>> print(f"Orphan pages: {len(link_report.orphan_pages)}")
"""

from webcrawler.analyzers.robots_parser import RobotsParser
from webcrawler.analyzers.sitemap_parser import SitemapParser
from webcrawler.analyzers.content_analyzer import (
    ContentAnalyzer,
    ContentIssue,
    ContentAnalysisReport,
    IssueSeverity,
)
from webcrawler.analyzers.link_extractor import (
    LinkExtractor,
    LinkAnalysis,
    PageLinkMetrics,
    LinkExtractionReport,
    AnchorTextAnalyzer,
)
from webcrawler.analyzers.stats_calculator import (
    StatsCalculator,
    CrawlStatistics,
)

__all__ = [
    # Robots & Sitemap
    "RobotsParser",
    "SitemapParser",
    # Content Analysis
    "ContentAnalyzer",
    "ContentIssue",
    "ContentAnalysisReport",
    "IssueSeverity",
    # Link Analysis
    "LinkExtractor",
    "LinkAnalysis",
    "PageLinkMetrics",
    "LinkExtractionReport",
    "AnchorTextAnalyzer",
    # Statistics
    "StatsCalculator",
    "CrawlStatistics",
]
