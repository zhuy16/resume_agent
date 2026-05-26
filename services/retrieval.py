"""
Retrieval service for ChromaDB vector search operations.
"""

from typing import Dict, Any, Optional


class RetrievalService:
    """Service for querying job description embeddings from ChromaDB."""
    
    def __init__(self, collection):
        """
        Initialize with ChromaDB collection.
        
        Args:
            collection: ChromaDB collection instance
        """
        self._collection = collection
    
    def query_similar_jobs(
        self,
        jd_text: str,
        n_results: int = 3,
        filter_outcome: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Query ChromaDB for similar job descriptions.
        
        Args:
            jd_text: Job description text to query
            n_results: Number of results to return
            filter_outcome: Optional filter by outcome (e.g., 'applied', 'interviewed')
            
        Returns:
            Dict with keys: documents, metadatas, distances
        """
        # Build where clause if outcome filter provided
        where_clause = {"outcome": filter_outcome} if filter_outcome else None
        
        results = self._collection.query(
            query_texts=[jd_text],
            n_results=n_results,
            where=where_clause if where_clause else None,
        )
        
        return {
            "documents": results["documents"][0],
            "metadatas": results["metadatas"][0],
            "distances": results["distances"][0],
        }
    
    def get_job_by_path(self, path: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a specific job by its file path.
        
        Args:
            path: File path of the job description
            
        Returns:
            Job metadata or None if not found
        """
        results = self._collection.get(where={"path": path})
        
        if results["ids"]:
            return {
                "id": results["ids"][0],
                "document": results["documents"][0] if results["documents"] else None,
                "metadata": results["metadatas"][0] if results["metadatas"] else None,
            }
        return None
    
    def ingest_job_description(self, path: str, text: str, metadata: Dict[str, Any]) -> str:
        """
        Ingest a new job description into the vector database.
        
        Args:
            path: File path of the job description
            text: Extracted text content
            metadata: Additional metadata (job_folder, outcome, filename, etc.)
            
        Returns:
            ID of the inserted document
        """
        import uuid
        
        doc_id = str(uuid.uuid4())
        
        self._collection.add(
            ids=[doc_id],
            documents=[text],
            metadatas=[{**metadata, "path": path}],
        )
        
        return doc_id
    
    def check_exists(self, path: str) -> bool:
        """Check if a job description already exists in the database."""
        results = self._collection.get(where={"path": path})
        return len(results["ids"]) > 0
