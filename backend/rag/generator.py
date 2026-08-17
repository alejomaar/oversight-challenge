"""
RAG generator using AWS Bedrock for answer generation.
"""

import logging
import re
from typing import Dict, List
from datetime import datetime
from langchain_aws import ChatBedrock
from langchain_core.messages import HumanMessage

from core.config import settings
from rag.retriever import Retriever

logger = logging.getLogger(__name__)


class Generator:
    """Handles RAG pipeline and answer generation using AWS Bedrock."""
    
    RAG_PROMPT_TEMPLATE = """You are an AI Knowledge Base Assistant that answers questions STRICTLY based on the provided document context from uploaded files ONLY.

CRITICAL RULES - YOU MUST FOLLOW THESE STRICTLY:
1. You MUST ONLY use information from the provided document context below
2. DO NOT use any external knowledge, general information, or information from other sources
3. DO NOT make assumptions or add information not present in the uploaded documents
4. If the answer is not in the context, you MUST say: "I don't have information about this in the uploaded documents. Please upload relevant documents or rephrase your question."
5. Format your answer in POINT-WISE format using bullet points
6. If the context doesn't fully answer the question, acknowledge what information is available and what is missing

User Question:
{question}

Document Context (from uploaded files only):
{context}

Additional Mode:
Explain like I'm 10: {explain_mode}

Instructions:
1. FIRST: Carefully analyze the question to understand what specific information is being asked
2. SECOND: Search through the provided document context to find relevant information
3. THIRD: Synthesize the information maintaining accuracy to the original text
4. FOURTH: Format your response in POINT-WISE format with bullet points

Return your response in this format:
ANSWER: [Your point-wise answer here - based ONLY on the document context, formatted with bullet points]

SOURCES: [List all sources used from the documents]
"""
    
    def __init__(self, retriever: Retriever):
        """Initialize generator with AWS Bedrock."""
        try:
            self.model = ChatBedrock(
                model_id=settings.BEDROCK_LLM_MODEL_ID,
                region_name=settings.AWS_REGION,
                model_kwargs={
                    "temperature": settings.TEMPERATURE,
                    "max_tokens": settings.MAX_TOKENS,
                }
            )
            logger.info(f"Using Bedrock model: {settings.BEDROCK_LLM_MODEL_ID}")
        except Exception as e:
            logger.error(f"Failed to initialize Bedrock client: {str(e)}")
            raise ValueError(f"Failed to initialize Bedrock client: {str(e)}")

        self.retriever = retriever
    
    def generate_answer(self, question: str, explain_like_10: bool = False, top_k: int = None) -> Dict:
        """
        Generate an answer using RAG pipeline.
        
        Args:
            question: User question
            explain_like_10: Whether to simplify the explanation
            top_k: Number of chunks to retrieve
            
        Returns:
            Dictionary with answer, sources, confidence score, etc.
        """
        if top_k is None:
            top_k = settings.TOP_K_CHUNKS
        
        if not question or not question.strip():
            return {
                'answer': "Please provide a valid question.",
                'sources': [],
                'confidence_score': 0.0,
                'similarity_scores': []
            }
        
        try:
            retrieved_docs_with_scores = self.retriever.retrieve_with_scores(question, k=top_k)
            
            if not retrieved_docs_with_scores:
                return {
                    'answer': "I couldn't find any relevant information in the knowledge base. Please make sure documents have been uploaded and processed.",
                    'sources': [],
                    'confidence_score': 0.0,
                    'similarity_scores': []
                }
            
            retrieved_docs = [doc for doc, score in retrieved_docs_with_scores]
            similarity_scores = [score for doc, score in retrieved_docs_with_scores]
            
            # Calculate confidence score
            confidence_score = 0.0
            confidence_breakdown = None
            
            if similarity_scores:
                best_distance = min(similarity_scores)
                avg_distance = sum(similarity_scores) / len(similarity_scores)
                
                best_similarity = max(0.0, 1.0 - (best_distance / 2.0))
                avg_similarity = max(0.0, 1.0 - (avg_distance / 2.0))
                
                if len(similarity_scores) > 1:
                    variance = sum((s - avg_distance) ** 2 for s in similarity_scores) / len(similarity_scores)
                    consistency = 1.0 / (1.0 + variance)
                else:
                    consistency = 1.0
                
                query_lower = question.lower()
                keyword_matches = 0
                for doc in retrieved_docs:
                    content_lower = doc.page_content.lower()
                    query_words = set(re.findall(r'\b\w+\b', query_lower))
                    content_words = set(re.findall(r'\b\w+\b', content_lower))
                    matches = len(query_words.intersection(content_words))
                    if matches > 0:
                        keyword_matches += matches / len(query_words) if query_words else 0
                
                keyword_boost = min(1.0, keyword_matches / len(retrieved_docs)) if retrieved_docs else 0.0

                weights = [float(w) for w in settings.CONFIDENCE_SCORE_WEIGHTS.split(':')]
                confidence_score = (
                    weights[0] * best_similarity +
                    weights[1] * avg_similarity +
                    weights[2] * consistency +
                    weights[3] * keyword_boost
                )

                confidence_score = confidence_score ** settings.CONFIDENCE_SCORE_POWER
                confidence_score = max(0.0, min(1.0, confidence_score))
                
                confidence_breakdown = {
                    'best_similarity': best_similarity,
                    'avg_similarity': avg_similarity,
                    'consistency': consistency,
                    'keyword_match': keyword_boost,
                    'final_score': confidence_score
                }
            
            # Format context and generate answer
            context = self.retriever.format_context(retrieved_docs)
            
            prompt = self.RAG_PROMPT_TEMPLATE.format(
                question=question,
                context=context,
                explain_mode="Yes" if explain_like_10 else "No"
            )

            response = self.model.invoke([HumanMessage(content=prompt)])
            answer_text = response.content
            answer = self._extract_answer(answer_text)
            sources = self.retriever.get_source_metadata(retrieved_docs)
            
            # Add similarity scores to sources
            for i, source in enumerate(sources):
                if i < len(similarity_scores):
                    source['similarity_score'] = float(1.0 - (similarity_scores[i] / 2.0))
            
            return {
                'answer': answer,
                'sources': sources,
                'confidence_score': confidence_score,
                'confidence_breakdown': confidence_breakdown,
                'similarity_scores': [float(1.0 - (s / 2.0)) for s in similarity_scores],
                'query': question,
                'timestamp': datetime.utcnow(),
                'explain_mode': explain_like_10
            }
            
        except Exception as e:
            logger.error(f"Error generating answer: {str(e)}")
            return {
                'answer': f"An error occurred while generating the answer: {str(e)}",
                'sources': [],
                'confidence_score': 0.0,
                'similarity_scores': [],
                'confidence_breakdown': None,
                'query': question,
                'timestamp': datetime.utcnow(),
                'explain_mode': explain_like_10
            }
    
    def _extract_answer(self, response_text: str) -> str:
        """Extract answer from response text."""
        if "ANSWER:" in response_text:
            parts = response_text.split("ANSWER:")
            if len(parts) > 1:
                answer = parts[1].split("SOURCES:")[0].strip()
                return answer
        return response_text.split("SOURCES:")[0].strip() if "SOURCES:" in response_text else response_text.strip()

