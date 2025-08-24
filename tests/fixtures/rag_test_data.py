"""
Test data fixtures for RAG quality integration tests.

This module provides consistent biomedical test documents for testing RAG
improvements like section boosting, query enhancement, and abstract reconstruction.
"""

from datetime import UTC, datetime
from typing import Any

from bio_mcp.models.document import Document


def get_biomedical_test_documents() -> list[Document]:
    """
    Get standardized biomedical test documents for RAG integration tests.
    
    These documents are designed to test:
    - Section boosting (Results, Conclusions, Methods, Background)
    - Query enhancement (diabetes, COVID-19, cancer, heart disease terms)
    - Abstract reconstruction without title duplication
    - Quality scoring with different scores
    
    Returns:
        List of Document objects ready for chunking and storage
    """
    return [
        Document(
            uid="pubmed:12345678",
            source="pubmed",
            source_id="12345678",
            title="Diabetes Treatment with Metformin: Clinical Trial Results",
            text="""Background: Type 2 diabetes mellitus affects millions of patients worldwide. Current treatment strategies focus on glycemic control through various therapeutic approaches.

Methods: We conducted a randomized controlled trial with 500 patients diagnosed with type 2 diabetes. Patients were randomly assigned to receive metformin or placebo for 12 weeks. Primary endpoint was HbA1c reduction.

Results: Metformin treatment resulted in significant HbA1c reduction of 1.2% compared to placebo (p<0.001). Fasting glucose levels decreased by 45 mg/dL in the treatment group. Side effects were minimal and included mild gastrointestinal symptoms in 15% of patients.

Conclusions: Metformin therapy demonstrates superior efficacy for glycemic control in type 2 diabetes patients. The treatment is well-tolerated and should be considered as first-line therapy for diabetes management.""",
            published_at=datetime(2023, 6, 15, tzinfo=UTC),
            identifiers={"pmid": "12345678", "doi": "10.1000/test.2023.001"},
            authors=["Smith J", "Johnson M", "Williams K"],
            detail={
                "journal": "Journal of Diabetes Research", 
                "pub_types": ["Randomized Controlled Trial", "Clinical Trial"]
            }
        ),
        
        Document(
            uid="pubmed:87654321", 
            source="pubmed",
            source_id="87654321",
            title="Cancer Immunotherapy with Checkpoint Inhibitors: Systematic Review",
            text="""Background: Immune checkpoint inhibitors have revolutionized cancer treatment across multiple tumor types. Understanding their mechanisms of action and clinical efficacy is crucial for optimal patient care.

Methods: We performed a systematic review of randomized controlled trials evaluating PD-1 and PD-L1 inhibitors in solid tumors. Studies published between 2015-2023 were included. Primary outcomes included overall survival and progression-free survival.

Results: Analysis of 45 trials involving 15,000 patients showed significant improvement in overall survival with checkpoint inhibitors versus standard chemotherapy (HR 0.72, 95% CI 0.65-0.80). Response rates were higher in patients with high PD-L1 expression. Grade 3-4 immune-related adverse events occurred in 12% of patients.

Conclusions: Checkpoint inhibitors provide durable clinical benefit across multiple cancer types. Biomarker-guided therapy and careful monitoring for immune-related adverse events are essential for optimal outcomes.""",
            published_at=datetime(2023, 8, 22, tzinfo=UTC),
            identifiers={"pmid": "87654321", "doi": "10.1000/test.2023.002"},
            authors=["Anderson R", "Brown L", "Davis P"],
            detail={
                "journal": "Cancer Treatment Reviews",
                "pub_types": ["Systematic Review", "Meta-Analysis"] 
            }
        ),
        
        Document(
            uid="pubmed:11111111",
            source="pubmed",
            source_id="11111111",
            title="COVID-19 Treatment Efficacy: Real-World Evidence Study",
            text="""Background: The COVID-19 pandemic has necessitated rapid evaluation of therapeutic interventions. Real-world evidence provides important insights into treatment effectiveness outside of controlled trial settings.

Methods: We analyzed electronic health records from 10,000 COVID-19 patients treated across 50 hospitals between 2020-2022. Treatment protocols included antiviral therapy, corticosteroids, and monoclonal antibodies. Primary outcome was 30-day mortality.

Results: Antiviral treatment within 5 days of symptom onset reduced mortality by 35% (OR 0.65, 95% CI 0.52-0.81). Early corticosteroid administration in severe cases decreased ICU length of stay by 3.2 days on average. Monoclonal antibody therapy showed greatest benefit in immunocompromised patients.

Conclusions: Early intervention with evidence-based COVID-19 therapies significantly improves clinical outcomes. Treatment timing and patient selection are critical factors for therapeutic success.""",
            published_at=datetime(2022, 12, 10, tzinfo=UTC),
            identifiers={"pmid": "11111111", "doi": "10.1000/test.2022.001"},
            authors=["Miller T", "Wilson S", "Taylor A"], 
            detail={
                "journal": "The Lancet Infectious Diseases",
                "pub_types": ["Observational Study", "Real-World Evidence"]
            }
        ),
        
        Document(
            uid="pubmed:22222222",
            source="pubmed",
            source_id="22222222",
            title="Heart Disease Prevention Through Lifestyle Modification",
            text="""Background: Cardiovascular disease remains the leading cause of mortality worldwide. Lifestyle interventions offer promising approaches for primary prevention of heart disease in high-risk populations.

Methods: We conducted a prospective cohort study following 2,500 adults with cardiovascular risk factors for 5 years. Interventions included dietary counseling, exercise programs, and smoking cessation support. Primary endpoint was incidence of major adverse cardiovascular events.

Results: Comprehensive lifestyle intervention reduced cardiovascular events by 42% compared to usual care (HR 0.58, 95% CI 0.45-0.75). Weight reduction averaged 8.5 kg in the intervention group. Blood pressure decreased by 12/8 mmHg and LDL cholesterol fell by 25 mg/dL.

Conclusions: Structured lifestyle modification programs provide substantial cardiovascular risk reduction. Implementation of such programs should be prioritized in primary care settings for high-risk patients.""",
            published_at=datetime(2023, 3, 8, tzinfo=UTC),
            identifiers={"pmid": "22222222", "doi": "10.1000/test.2023.003"},
            authors=["Garcia M", "Rodriguez C", "Martinez L"],
            detail={
                "journal": "American Heart Journal",
                "pub_types": ["Prospective Study", "Clinical Trial"]
            }
        ),
        
        # Additional document for testing edge cases
        Document(
            uid="pubmed:33333333",
            source="pubmed",
            source_id="33333333",
            title="Machine Learning in Drug Discovery: Neural Network Approaches",
            text="""Background: Machine learning applications in pharmaceutical research have expanded rapidly. Neural networks offer powerful tools for drug discovery and development.

Methods: We developed a deep learning framework using convolutional neural networks to predict molecular properties. Training data included 100,000 compounds with known bioactivity profiles. Model validation used cross-validation and external test sets.

Results: The neural network achieved 85% accuracy in predicting drug-target interactions. Feature importance analysis revealed key molecular descriptors. Processing time was reduced by 75% compared to traditional screening methods.

Conclusions: Deep learning accelerates drug discovery pipelines while maintaining high accuracy. Integration with existing pharmaceutical workflows is feasible and beneficial.""",
            published_at=datetime(2023, 11, 5, tzinfo=UTC),
            identifiers={"pmid": "33333333", "doi": "10.1000/test.2023.004"},
            authors=["Chen L", "Park S", "Kumar R"],
            detail={
                "journal": "Nature Biotechnology",
                "pub_types": ["Original Research", "Machine Learning"]
            }
        )
    ]


def get_quality_scores() -> list[float]:
    """
    Get quality scores corresponding to the test documents.
    
    Returns scores in the same order as get_biomedical_test_documents().
    Designed to test quality boosting functionality.
    
    Returns:
        List of quality scores from 0.8 to 1.0
    """
    return [0.85, 0.90, 0.95, 1.0, 0.80]


def get_expected_sections() -> list[list[str]]:
    """
    Get expected sections for each test document after chunking.
    
    Returns:
        List of section lists for each document
    """
    return [
        ["Background", "Methods", "Results", "Conclusions"],  # Diabetes paper
        ["Background", "Methods", "Results", "Conclusions"],  # Cancer paper
        ["Background", "Methods", "Results", "Conclusions"],  # COVID paper
        ["Background", "Methods", "Results", "Conclusions"],  # Heart disease paper
        ["Background", "Methods", "Results", "Conclusions"],  # ML paper
    ]


def get_test_queries() -> dict[str, Any]:
    """
    Get test queries designed to test specific RAG improvements.
    
    Returns:
        Dictionary mapping query types to query strings and expected behaviors
    """
    return {
        "diabetes": {
            "query": "diabetes treatment",
            "expected_enhancement": True,
            "should_find_docs": ["12345678"],
            "enhanced_terms": ["diabetes mellitus", "diabetic"]
        },
        "covid": {
            "query": "COVID-19 treatment", 
            "expected_enhancement": True,
            "should_find_docs": ["11111111"],
            "enhanced_terms": ["coronavirus", "SARS-CoV-2"]
        },
        "cancer": {
            "query": "cancer immunotherapy",
            "expected_enhancement": True, 
            "should_find_docs": ["87654321"],
            "enhanced_terms": ["neoplasm", "tumor", "malignancy"]
        },
        "heart_disease": {
            "query": "heart disease prevention",
            "expected_enhancement": True,
            "should_find_docs": ["22222222"], 
            "enhanced_terms": ["cardiovascular disease", "cardiac"]
        },
        "clinical_trial": {
            "query": "clinical trial efficacy",
            "expected_enhancement": True,
            "should_find_docs": ["12345678", "87654321", "11111111"],
            "enhanced_terms": ["randomized controlled"]
        }
    }