"""
Biomedical test data generator for MCP tools testing.

Provides realistic test data for cancer research, immunotherapy, and ML medicine papers
to validate MCP tools with authentic biomedical scenarios.
"""

from dataclasses import dataclass
from typing import Any, ClassVar


@dataclass
class TestPaper:
    """Test paper data structure matching real PubMed format."""

    pmid: str
    title: str
    abstract: str
    journal: str
    publication_date: str
    mesh_terms: list[str]
    authors: list[str]
    doi: str = ""
    keywords: list[str] = None

    def to_document_dict(self) -> dict[str, Any]:
        """Convert to format expected by document service."""
        return {
            "pmid": self.pmid,
            "title": self.title,
            "abstract": self.abstract,
            "journal": self.journal,
            "publication_date": self.publication_date,
            "mesh_terms": self.mesh_terms or [],
            "authors": self.authors,
            "doi": self.doi,
            "keywords": self.keywords or [],
            "source": "pubmed",
            "source_id": self.pmid,
            "id": f"pubmed:{self.pmid}",
        }


class BiomedicTestCorpus:
    """Realistic biomedical test data for MCP tools validation."""

    # Cancer research papers (realistic PMIDs and metadata)
    CANCER_PAPERS: ClassVar[list[TestPaper]] = [
        TestPaper(
            pmid="36653448",
            title="Glioblastoma multiforme: pathogenesis and treatment",
            abstract="Glioblastoma multiforme (GBM) is the most aggressive primary brain tumor with a median survival of 12-15 months. Current treatment involves maximal surgical resection followed by radiation and temozolomide chemotherapy. Recent advances in molecular characterization have identified key genetic alterations including EGFR amplification, TP53 mutations, and IDH status that influence prognosis and treatment response.",
            journal="Nature Reviews Cancer",
            publication_date="2023-01-18",
            mesh_terms=[
                "Glioblastoma",
                "Brain Neoplasms",
                "Antineoplastic Agents",
                "Radiation Therapy",
            ],
            authors=["Smith, J.", "Johnson, A.", "Wilson, R."],
            doi="10.1038/s41568-023-00547-8",
        ),
        TestPaper(
            pmid="35987654",
            title="CRISPR-Cas9 gene editing for cancer therapy: current status and future directions",
            abstract="CRISPR-Cas9 technology has emerged as a powerful tool for cancer treatment through targeted gene editing. Clinical applications include CAR-T cell engineering, tumor suppressor gene restoration, and oncogene knockout strategies. Recent trials have shown promising results in treating hematologic malignancies with engineered immune cells.",
            journal="Nature Medicine",
            publication_date="2022-11-15",
            mesh_terms=[
                "CRISPR-Cas Systems",
                "Gene Editing",
                "Neoplasms",
                "Immunotherapy",
            ],
            authors=["Chen, L.", "Martinez, P.", "Thompson, K."],
            doi="10.1038/s41591-022-02087-4",
        ),
        TestPaper(
            pmid="34567890",
            title="Liquid biopsy for cancer diagnosis and monitoring: clinical applications",
            abstract="Liquid biopsy represents a minimally invasive approach to cancer diagnosis through analysis of circulating tumor cells (CTCs), cell-free DNA (cfDNA), and exosomes in blood samples. This technology enables early detection, treatment monitoring, and resistance tracking without tissue biopsies.",
            journal="Journal of Clinical Oncology",
            publication_date="2022-08-10",
            mesh_terms=[
                "Liquid Biopsy",
                "Circulating Tumor Cells",
                "Cell-Free Nucleic Acids",
                "Biomarkers",
            ],
            authors=["Lee, S.", "Patel, R.", "Anderson, M."],
            doi="10.1200/JCO.22.00547",
        ),
    ]

    # Immunotherapy studies
    IMMUNOTHERAPY_PAPERS: ClassVar[list[TestPaper]] = [
        TestPaper(
            pmid="33445566",
            title="Checkpoint inhibitor immunotherapy: mechanisms and clinical outcomes",
            abstract="Immune checkpoint inhibitors targeting PD-1, PD-L1, and CTLA-4 have revolutionized cancer treatment. These agents work by blocking inhibitory signals that prevent T cell activation against tumor cells. Clinical trials have demonstrated significant survival benefits across multiple cancer types including melanoma, lung cancer, and kidney cancer.",
            journal="New England Journal of Medicine",
            publication_date="2022-03-22",
            mesh_terms=[
                "Immunotherapy",
                "Programmed Cell Death 1 Receptor",
                "CTLA-4 Antigen",
                "Melanoma",
            ],
            authors=["Rodriguez, A.", "Kim, H.", "Brown, D."],
            doi="10.1056/NEJMra2035922",
        ),
        TestPaper(
            pmid="32123456",
            title="CAR-T cell therapy for B-cell malignancies: manufacturing and clinical considerations",
            abstract="Chimeric antigen receptor T (CAR-T) cell therapy involves genetically modifying patient T cells to target specific cancer antigens. FDA-approved CAR-T therapies for B-cell leukemia and lymphoma have shown remarkable response rates, though challenges include cytokine release syndrome and neurotoxicity.",
            journal="Blood",
            publication_date="2021-12-05",
            mesh_terms=[
                "Immunotherapy, Adoptive",
                "Receptors, Chimeric Antigen",
                "Precursor Cell Lymphoblastic Leukemia-Lymphoma",
                "T-Lymphocytes",
            ],
            authors=["Williams, J.", "Zhang, Q.", "Miller, T."],
            doi="10.1182/blood.2021013760",
        ),
    ]

    # Machine learning in medicine papers
    ML_MEDICINE_PAPERS: ClassVar[list[TestPaper]] = [
        TestPaper(
            pmid="31789012",
            title="Deep learning for medical image analysis: applications in radiology and pathology",
            abstract="Deep learning algorithms, particularly convolutional neural networks, have shown exceptional performance in medical image analysis. Applications include automated detection of skin cancer from dermoscopy images, lung nodule identification in CT scans, and histopathological cancer diagnosis with accuracy matching expert pathologists.",
            journal="Nature Reviews Clinical Oncology",
            publication_date="2021-09-14",
            mesh_terms=[
                "Deep Learning",
                "Radiology",
                "Pathology",
                "Medical Imaging",
                "Artificial Intelligence",
            ],
            authors=["Liu, X.", "Singh, A.", "Johnson, P."],
            doi="10.1038/s41571-021-00523-2",
        ),
        TestPaper(
            pmid="30456789",
            title="Machine learning prediction models for cancer prognosis: systematic review",
            abstract="Machine learning approaches including random forests, support vector machines, and neural networks are increasingly used for cancer prognosis prediction. Models incorporating genomic data, clinical variables, and imaging features show improved accuracy over traditional prognostic scores, enabling personalized treatment decisions.",
            journal="The Lancet Oncology",
            publication_date="2021-06-08",
            mesh_terms=[
                "Machine Learning",
                "Prognosis",
                "Neoplasms",
                "Precision Medicine",
            ],
            authors=["Taylor, R.", "Garcia, M.", "Wong, C."],
            doi="10.1016/S1470-2045(21)00241-3",
        ),
    ]

    # Clinical trial checkpoint scenarios for corpus testing
    CHECKPOINT_SCENARIOS: ClassVar[list[dict[str, Any]]] = [
        {
            "checkpoint_id": "cancer_immunotherapy_2024",
            "name": "Cancer Immunotherapy Research 2024",
            "description": "Comprehensive checkpoint for cancer immunotherapy research papers from 2024",
            "query": "cancer immunotherapy checkpoint inhibitor 2024[PDAT]",
            "expected_papers": 1250,
            "last_sync_edat": "2024-01-15",
            "version": "1.0",
        },
        {
            "checkpoint_id": "glioblastoma_treatment",
            "name": "Glioblastoma Treatment Studies",
            "description": "Focused checkpoint for glioblastoma treatment research",
            "query": "glioblastoma treatment therapy",
            "expected_papers": 850,
            "last_sync_edat": "2024-01-10",
            "version": "2.1",
        },
        {
            "checkpoint_id": "crispr_cancer_trials",
            "name": "CRISPR Cancer Clinical Trials",
            "description": "Checkpoint for CRISPR-based cancer therapy clinical trials",
            "query": "CRISPR cancer clinical trial",
            "expected_papers": 320,
            "last_sync_edat": "2024-01-08",
            "version": "1.5",
        },
    ]

    @property
    def all_papers(self) -> list[TestPaper]:
        """Return all test papers across all categories."""
        return self.CANCER_PAPERS + self.IMMUNOTHERAPY_PAPERS + self.ML_MEDICINE_PAPERS

    def get_papers_by_category(self, category: str) -> list[TestPaper]:
        """Get papers by category name."""
        categories = {
            "cancer": self.CANCER_PAPERS,
            "immunotherapy": self.IMMUNOTHERAPY_PAPERS,
            "ml_medicine": self.ML_MEDICINE_PAPERS,
        }
        return categories.get(category, [])

    def get_paper_by_pmid(self, pmid: str) -> TestPaper:
        """Get specific paper by PMID."""
        for paper in self.all_papers:
            if paper.pmid == pmid:
                return paper
        raise ValueError(f"No test paper found with PMID: {pmid}")

    def get_search_test_cases(self) -> list[dict[str, Any]]:
        """Get test cases for search functionality."""
        return [
            {
                "query": "glioblastoma treatment",
                "expected_pmids": ["36653448"],
                "description": "Brain cancer treatment query",
            },
            {
                "query": "CRISPR gene editing cancer",
                "expected_pmids": ["35987654"],
                "description": "Gene editing technology query",
            },
            {
                "query": "checkpoint inhibitor immunotherapy",
                "expected_pmids": ["33445566"],
                "description": "Immunotherapy mechanism query",
            },
            {
                "query": "machine learning medical imaging",
                "expected_pmids": ["31789012"],
                "description": "AI in medicine query",
            },
            {
                "query": "liquid biopsy cancer diagnosis",
                "expected_pmids": ["34567890"],
                "description": "Diagnostic technology query",
            },
        ]

    def create_quality_test_papers(self) -> list[TestPaper]:
        """Create papers with different quality scores for ranking tests."""
        return [
            TestPaper(
                pmid="99999001",
                title="High-impact Nature cancer study",
                abstract="Breakthrough cancer research published in Nature with high citation count.",
                journal="Nature",
                publication_date="2023-06-15",
                mesh_terms=["Neoplasms", "Breakthrough Therapy"],
                authors=["Expert, A.", "Leader, B."],
            ),
            TestPaper(
                pmid="99999002",
                title="Local journal cancer study",
                abstract="Similar cancer research but published in lower-impact journal.",
                journal="Local Medical Journal",
                publication_date="2023-06-14",
                mesh_terms=["Neoplasms", "Therapy"],
                authors=["Researcher, C.", "Student, D."],
            ),
        ]
