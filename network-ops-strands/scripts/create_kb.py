#!/usr/bin/env python3
"""Create a Bedrock Knowledge Base with S3 Vectors storage.

Creates the S3 vector bucket + index, then the KB + data source,
and triggers ingestion.
"""
import argparse
import json
import sys
import time

import boto3


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True)
    parser.add_argument("--role-arn", required=True)
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--bucket", required=True, help="S3 data bucket")
    parser.add_argument("--prefix", default="knowledge-base/")
    args = parser.parse_args()

    region = args.region
    role_arn = args.role_arn
    role_name = role_arn.split("/")[-1]
    vector_bucket = f"{args.name}-vectors"
    index_name = f"{args.name}-index"

    s3v = boto3.client("s3vectors", region_name=region)
    bedrock = boto3.client("bedrock-agent", region_name=region)
    iam = boto3.client("iam")

    # Step 1: Create S3 vector bucket
    print("Creating S3 vector bucket...", file=sys.stderr)
    try:
        s3v.create_vector_bucket(vectorBucketName=vector_bucket)
        print(f"  Created: {vector_bucket}", file=sys.stderr)
    except Exception as e:
        if "Conflict" in type(e).__name__:
            print(f"  Already exists: {vector_bucket}", file=sys.stderr)
        else:
            print(f"  Error: {e}", file=sys.stderr)
            sys.exit(1)

    # Step 2: Create vector index
    print("Creating vector index...", file=sys.stderr)
    try:
        s3v.create_index(
            vectorBucketName=vector_bucket,
            indexName=index_name,
            dimension=1024,
            distanceMetric="cosine",
            dataType="float32",
        )
        print(f"  Created: {index_name}", file=sys.stderr)
    except Exception as e:
        if "Conflict" in type(e).__name__:
            print(f"  Already exists: {index_name}", file=sys.stderr)
        else:
            print(f"  Error: {e}", file=sys.stderr)
            sys.exit(1)

    # Get index ARN
    idx = s3v.get_index(
        vectorBucketName=vector_bucket, indexName=index_name
    )
    index_arn = idx["index"]["indexArn"]
    bucket_arn = (
        idx["index"].get("vectorBucketArn")
        or f"arn:aws:s3vectors:{region}:{boto3.client('sts').get_caller_identity()['Account']}:bucket/{vector_bucket}"
    )
    print(f"  Index ARN: {index_arn}", file=sys.stderr)

    # Step 3: Update role with specific index permissions
    print("Updating role permissions...", file=sys.stderr)
    iam.put_role_policy(
        RoleName=role_name,
        PolicyName="S3VectorsIndex",
        PolicyDocument=json.dumps({
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Action": [
                    "s3vectors:PutVectors", "s3vectors:GetVectors",
                    "s3vectors:DeleteVectors", "s3vectors:QueryVectors",
                    "s3vectors:GetIndex",
                ],
                "Resource": index_arn,
            }],
        }),
    )
    time.sleep(10)

    # Step 4: Create Knowledge Base
    print("Creating Knowledge Base...", file=sys.stderr)
    for attempt in range(4):
        try:
            r = bedrock.create_knowledge_base(
                name=args.name,
                description="Network operations troubleshooting articles and incident tickets",
                roleArn=role_arn,
                knowledgeBaseConfiguration={
                    "type": "VECTOR",
                    "vectorKnowledgeBaseConfiguration": {
                        "embeddingModelArn": f"arn:aws:bedrock:{region}::foundation-model/amazon.titan-embed-text-v2:0",
                        "embeddingModelConfiguration": {
                            "bedrockEmbeddingModelConfiguration": {
                                "dimensions": 1024
                            }
                        },
                    },
                },
                storageConfiguration={
                    "type": "S3_VECTORS",
                    "s3VectorsConfiguration": {
                        "vectorBucketArn": bucket_arn,
                        "indexName": index_name,
                    },
                },
            )
            kb_id = r["knowledgeBase"]["knowledgeBaseId"]
            print(f"  KB created: {kb_id}", file=sys.stderr)
            break
        except Exception as e:
            print(f"  Attempt {attempt + 1} failed: {e}", file=sys.stderr)
            if attempt < 3:
                time.sleep(15)
            else:
                sys.exit(1)

    # Wait for ACTIVE
    for _ in range(30):
        status = bedrock.get_knowledge_base(knowledgeBaseId=kb_id)[
            "knowledgeBase"
        ]["status"]
        if status == "ACTIVE":
            break
        time.sleep(5)
    print(f"  KB status: {status}", file=sys.stderr)

    # Step 5: Create data source
    print("Creating data source...", file=sys.stderr)
    ds = bedrock.create_data_source(
        knowledgeBaseId=kb_id,
        name=f"{args.name}-s3-source",
        dataSourceConfiguration={
            "type": "S3",
            "s3Configuration": {
                "bucketArn": f"arn:aws:s3:::{args.bucket}",
                "inclusionPrefixes": [args.prefix],
            },
        },
    )
    ds_id = ds["dataSource"]["dataSourceId"]
    print(f"  Data source: {ds_id}", file=sys.stderr)

    # Step 6: Start ingestion
    bedrock.start_ingestion_job(knowledgeBaseId=kb_id, dataSourceId=ds_id)
    print("  Ingestion started", file=sys.stderr)

    # Output KB_ID to stdout
    print(kb_id)


if __name__ == "__main__":
    main()
