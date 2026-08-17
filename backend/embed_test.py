#!/usr/bin/env python3
import boto3
import json

def embed_text_titan():
    client = boto3.client('bedrock-runtime', region_name='us-east-1')

    text_to_embed = "Hello"

    payload = {
        "inputText": text_to_embed,
    }

    response = client.invoke_model(
        modelId="amazon.titan-embed-text-v2:0",
        contentType="application/json",
        accept="application/json",
        body=json.dumps(payload)
    )

    result = json.loads(response['body'].read())

    embedding = result.get('embedding', [])

    print(f"Text: '{text_to_embed}'")
    print(f"Embedding dimension: {len(embedding)}")
    print(f"First 10 values: {embedding[:10]}")
    print(f"\nFull embedding: {embedding}")

    return embedding

if __name__ == "__main__":
    embed_text_titan()
