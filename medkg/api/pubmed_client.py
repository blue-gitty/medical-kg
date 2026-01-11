"""
PubMed API Client (Entrez / BioPython)

This is intentionally based on the working approach in `templates.py`:
- Use BioPython's `Bio.Entrez` for `esearch` + `esummary`
- Return clean outputs: PMID + Title (and optional full-text signals)
"""

from __future__ import annotations

import os
import time
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PubMedArticle:
    pmid: str
    title: str
    journal: Optional[str] = None
    pubdate: Optional[str] = None
    doi: Optional[str] = None
    pmc_id: Optional[str] = None
    has_full_text: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pmid": self.pmid,
            "title": self.title,
            "journal": self.journal,
            "pubdate": self.pubdate,
            "doi": self.doi,
            "pmc_id": self.pmc_id,
            "has_full_text": self.has_full_text,
        }


class PubMedAPIClient:
    """
    PubMed client using NCBI E-utilities via BioPython Entrez.

    Outputs are designed for your workflow: for a query, show PMIDs + titles.
    """

    def __init__(
        self,
        email: Optional[str] = None,
        api_key: Optional[str] = None,
        tool: str = "MEDKG",
        requests_per_second: float = 3.0,
    ):
        try:
            from Bio import Entrez  # type: ignore
        except ImportError as e:
            raise ImportError(
                "BioPython is required for PubMed search. Install with: pip install biopython"
            ) from e

        self._Entrez = Entrez

        self.email = email or os.getenv("PUBMED_EMAIL", "")
        if not self.email:
            # NCBI strongly recommends providing an email
            logger.warning("PUBMED_EMAIL is not set; consider adding it to .env")

        self.api_key = api_key or os.getenv("PUBMED_API_KEY")
        if not self.api_key:
            logger.info("PUBMED_API_KEY not set; using unauthenticated access (slower).")

        # Configure Entrez globals
        self._Entrez.email = self.email
        if self.api_key:
            self._Entrez.api_key = self.api_key
        self._Entrez.tool = tool

        # Rate limiting (NCBI: ~3 req/sec without key; with key can be higher)
        self._min_interval = 1.0 / max(requests_per_second, 0.1)
        self._last_req_ts = 0.0

    def _rate_limit(self) -> None:
        now = time.time()
        dt = now - self._last_req_ts
        if dt < self._min_interval:
            time.sleep(self._min_interval - dt)
        self._last_req_ts = time.time()

    def _esearch(self, term: str, retmax: int, retstart: int = 0) -> List[str]:
        self._rate_limit()
        h = self._Entrez.esearch(
            db="pubmed",
            term=term,
            retmax=retmax,
            retstart=retstart,
            sort="relevance",
        )
        try:
            r = self._Entrez.read(h)
        finally:
            h.close()
        return [str(x) for x in r.get("IdList", [])]

    def _esummary_batch(self, pmids: List[str]) -> List[Dict[str, Any]]:
        if not pmids:
            return []
        self._rate_limit()
        h = self._Entrez.esummary(db="pubmed", id=",".join(pmids), retmode="xml")
        try:
            summaries = self._Entrez.read(h)
        finally:
            h.close()
        # Entrez.read can return a list-like object
        return list(summaries)

    @staticmethod
    def _extract_ids(article_ids: Any) -> Dict[str, str]:
        """
        `ArticleIds` shapes vary depending on Entrez/BioPython parsing.
        We normalize into a dict like: {"pmc": "PMCxxxx", "doi": "..."}.
        """
        out: Dict[str, str] = {}

        # Common case: list of dicts with IdType/Value
        if isinstance(article_ids, list):
            for item in article_ids:
                if isinstance(item, dict):
                    id_type = str(item.get("IdType", "")).lower()
                    val = str(item.get("Value", "")).strip()
                    if id_type and val:
                        out[id_type] = val
            return out

        # Sometimes: dict-like
        if isinstance(article_ids, dict):
            for k, v in article_ids.items():
                key = str(k).lower()
                if isinstance(v, list) and v:
                    out[key] = str(v[0])
                elif v is not None:
                    out[key] = str(v)
            return out

        return out

    @staticmethod
    def _has_full_text_signal(summary: Dict[str, Any]) -> bool:
        # Mirror `templates.py` intent: PMC id OR fulltext URLs
        article_ids = PubMedAPIClient._extract_ids(summary.get("ArticleIds"))
        if "pmc" in article_ids and article_ids["pmc"]:
            return True

        full_text_urls = summary.get("FullTextUrlList")
        if isinstance(full_text_urls, dict):
            url_list = full_text_urls.get("FullTextUrl", [])
            if isinstance(url_list, list):
                for url in url_list:
                    if isinstance(url, dict):
                        u = str(url.get("Url", ""))
                        if u.endswith(".pdf") or "full" in u.lower() or "pmc" in u.lower():
                            return True
        return False

    @staticmethod
    def _build_date_filter(start_date: Optional[str] = None, end_date: Optional[str] = None) -> str:
        """
        Build a PubMed date range filter string.
        
        Args:
            start_date: Start date in format "YYYY/MM/DD", "YYYY/MM", or "YYYY"
            end_date: End date in format "YYYY/MM/DD", "YYYY/MM", or "YYYY"
        
        Returns:
            Date filter string for PubMed query (e.g., "2020/01/01:2023/12/31[PDAT]")
        """
        if not start_date and not end_date:
            return ""
        
        # Validate and normalize date formats
        def normalize_date(date_str: str) -> str:
            """Normalize date string to PubMed format."""
            date_str = date_str.strip()
            # Accept YYYY, YYYY/MM, or YYYY/MM/DD
            parts = date_str.split("/")
            if len(parts) == 1:
                # YYYY
                if len(parts[0]) == 4 and parts[0].isdigit():
                    return parts[0]
            elif len(parts) == 2:
                # YYYY/MM
                if len(parts[0]) == 4 and parts[0].isdigit() and len(parts[1]) == 2 and parts[1].isdigit():
                    return f"{parts[0]}/{parts[1]}"
            elif len(parts) == 3:
                # YYYY/MM/DD
                if (len(parts[0]) == 4 and parts[0].isdigit() and 
                    len(parts[1]) == 2 and parts[1].isdigit() and 
                    len(parts[2]) == 2 and parts[2].isdigit()):
                    return f"{parts[0]}/{parts[1]}/{parts[2]}"
            raise ValueError(f"Invalid date format: {date_str}. Use YYYY, YYYY/MM, or YYYY/MM/DD")
        
        start_val = None
        end_val = None
        
        if start_date:
            start_val = normalize_date(start_date)
        if end_date:
            end_val = normalize_date(end_date)
        
        if start_val and end_val:
            # Date range: ensure start <= end
            return f"{start_val}:{end_val}[PDAT]"
        elif start_val:
            # From start_date onwards: use current year + 1 as end
            from datetime import datetime
            current_year = datetime.now().year
            end_val = f"{current_year + 1}/12/31"
            return f"{start_val}:{end_val}[PDAT]"
        elif end_val:
            # Up to end_date: use 1800 as start (PubMed's earliest reasonable date)
            start_val = "1800/01/01"
            return f"{start_val}:{end_val}[PDAT]"
        
        return ""

    def search(
        self,
        query: str,
        max_results: int = 20,
        full_text_only: bool = False,
        overfetch_factor: int = 5,
        max_pages: int = 10,
        use_smart_query: bool = True,
        return_query: bool = False,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search PubMed and return clean results with PMID + title.
        
        Args:
            query: User query (natural language) or PubMed query string
            max_results: Maximum number of results
            full_text_only: Filter to articles with PMC/full-text signal
            overfetch_factor: Multiplier for initial fetch (for full_text_only filtering)
            max_pages: Maximum pages to paginate (for full_text_only)
            use_smart_query: If True, convert user query to structured PubMed query via UMLS/MeSH
            return_query: If True, return dict with 'query' and 'results' keys instead of just results
            start_date: Start date for filtering (format: "YYYY/MM/DD", "YYYY/MM", or "YYYY")
            end_date: End date for filtering (format: "YYYY/MM/DD", "YYYY/MM", or "YYYY")
        
        Examples:
            # Search with date range
            client.search("intracranial aneurysm", start_date="2020/01/01", end_date="2023/12/31")
            
            # Search from a specific year onwards
            client.search("inflammation", start_date="2020")
            
            # Search up to a specific date
            client.search("hemodynamics", end_date="2022/12/31")
        """
        if not query or not query.strip():
            return [] if not return_query else {'query': query, 'original_query': None, 'results': []}
        
        original_query = query
        final_query = query
        
        # Convert user query to structured PubMed query using UMLS/MeSH
        if use_smart_query:
            try:
                from ..search.builder import query_to_pubmed_query
                final_query = query_to_pubmed_query(query, score_threshold=0.8)
                logger.debug(f"Smart query built: {final_query[:200]}...")
            except Exception as e:
                logger.warning(f"Smart query building failed, using raw query: {e}")
                final_query = query
        
        # Add date range filter if provided
        date_filter = self._build_date_filter(start_date, end_date)
        if date_filter:
            final_query = f"({final_query}) AND {date_filter}"
            logger.debug(f"Date filter applied: {date_filter}")
        
        query = final_query

        # If full_text_only=True, we may need to page through search results to
        # collect enough full-text candidates.
        needed = max_results
        collected_pmids: List[str] = []
        seen: set[str] = set()

        if full_text_only:
            page_size = max(50, max_results * overfetch_factor)
            retstart = 0
            for _ in range(max_pages):
                pmids_page = self._esearch(query.strip(), retmax=page_size, retstart=retstart)
                if not pmids_page:
                    break
                for pmid in pmids_page:
                    if pmid not in seen:
                        collected_pmids.append(pmid)
                        seen.add(pmid)
                retstart += page_size
                # Stop paging if we have a decent pool to summarize
                if len(collected_pmids) >= needed * overfetch_factor:
                    break
            pmids = collected_pmids
        else:
            pmids = self._esearch(query.strip(), retmax=max_results)

        if not pmids:
            return []

        results: List[PubMedArticle] = []
        batch_size = 50
        for i in range(0, len(pmids), batch_size):
            batch_pmids = pmids[i : i + batch_size]
            summaries = self._esummary_batch(batch_pmids)

            for s in summaries:
                pmid = str(s.get("Id", "")).strip()
                title = str(s.get("Title", "")).strip()
                journal = str(s.get("FullJournalName", "")).strip() or None
                pubdate = str(s.get("PubDate", "")).strip() or None

                ids = self._extract_ids(s.get("ArticleIds"))
                doi = ids.get("doi")
                pmc_id = ids.get("pmc") or ids.get("pmcid")
                has_full_text = self._has_full_text_signal(s)

                if full_text_only and not has_full_text:
                    continue

                if not pmid:
                    continue

                results.append(
                    PubMedArticle(
                        pmid=pmid,
                        title=title,
                        journal=journal,
                        pubdate=pubdate,
                        doi=doi,
                        pmc_id=pmc_id,
                        has_full_text=has_full_text,
                    )
                )

                if len(results) >= max_results:
                    break

            if len(results) >= max_results:
                break

        results_list = [r.to_dict() for r in results]
        
        if return_query:
            return {
                'query': final_query,
                'original_query': original_query,
                'results': results_list
            }
        
        return results_list

    # Convenience alias for your intent (matches `templates.py` naming)
    def search_with_fulltext(
        self, 
        query: str, 
        max_results: int = 20,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        return self.search(
            query=query, 
            max_results=max_results, 
            full_text_only=True,
            start_date=start_date,
            end_date=end_date,
        )

