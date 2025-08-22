from datetime import datetime

from bio_mcp.models.document import Chunk, Document


class TestDocumentChunkIntegration:
    """Test Document and Chunk models working together."""

    def test_document_to_chunks_workflow(self):
        """Test typical document → chunks workflow."""
        # Create document
        doc = Document(
            uid="pubmed:12345678",
            source="pubmed",
            source_id="12345678",
            title="Biomedical Research Paper",
            text="Background: This study investigates... Methods: We conducted... Results: We found...",
            published_at=datetime(2024, 1, 15),
            authors=["Smith, J."],
            provenance={"s3_raw_uri": "s3://bucket/pubmed/12345678.json"},
            detail={
                "journal": "Nature Medicine",
                "mesh_terms": ["research", "biomedical"],
            },
        )

        # Simulate chunking process
        chunks = []
        sections = ["Background", "Methods", "Results"]
        texts = [
            "Background: This study investigates...",
            "Methods: We conducted...",
            "Results: We found...",
        ]

        for i, (section, text) in enumerate(zip(sections, texts)):
            chunk_id = f"s{i}"
            chunk = Chunk(
                chunk_id=chunk_id,
                uuid=Chunk.generate_uuid(doc.uid, chunk_id),
                parent_uid=doc.uid,
                source=doc.source,
                chunk_idx=i,
                text=text,
                title=doc.title,
                section=section,
                published_at=doc.published_at,
                tokens=len(text.split()),  # Rough approximation
                n_sentences=1,
                meta={
                    "chunker_version": "v1.2.0",
                    "tokenizer": "hf:pritamdeka/BioBERT",
                    "src": {"pubmed": doc.detail},
                },
            )
            chunks.append(chunk)

        # Verify relationships
        assert len(chunks) == 3
        for chunk in chunks:
            assert chunk.parent_uid == doc.uid
            assert chunk.source == doc.source
            assert chunk.title == doc.title
            assert chunk.published_at == doc.published_at
            assert chunk.meta["src"]["pubmed"]["journal"] == "Nature Medicine"

        # Verify deterministic UUIDs
        chunk_uuids = [chunk.uuid for chunk in chunks]
        assert len(set(chunk_uuids)) == 3  # All unique

        # Re-generate same chunks should have same UUIDs
        new_chunks = []
        for i, (section, text) in enumerate(zip(sections, texts)):
            chunk_id = f"s{i}"
            new_chunk = Chunk(
                chunk_id=chunk_id,
                uuid=Chunk.generate_uuid(doc.uid, chunk_id),
                parent_uid=doc.uid,
                source=doc.source,
                chunk_idx=i,
                text=text,
                title=doc.title,
                section=section,
            )
            new_chunks.append(new_chunk)

        for original, regenerated in zip(chunks, new_chunks):
            assert original.uuid == regenerated.uuid
