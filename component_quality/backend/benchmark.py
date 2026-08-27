import asyncio
import time
import httpx
import sys

BASE_URL = "http://127.0.0.1:9000"
SUPERVISOR_ID = "1312c3b9-d038-41e7-addd-bf7d374dfcd3"

async def create_setup(client):
    # Create student
    import uuid
    res = await client.post(f"{BASE_URL}/supervisors/{SUPERVISOR_ID}/students", json={
        "full_name": "Benchmark Student",
        "email": f"bench_{uuid.uuid4().hex[:6]}@example.com",
        "academic_student_id": f"BENCH-{uuid.uuid4().hex[:6]}"
    })
    if res.status_code not in (200, 201):
        print("Failed to create student:", res.status_code, res.text)
        sys.exit(1)
    student_id = res.json()["student_id"]
    
    # Create proposal
    res = await client.post(f"{BASE_URL}/students/{student_id}/proposals", json={
        "title": "Benchmark Proposal",
        "description": "Benchmarking performance."
    })
    proposal_id = res.json()["proposal_id"]
    
    # Create version
    valid_text = """
    Abstract: This research studies ML performance.
    Introduction: Concurrent analysis is a bottleneck.
    Objectives: To optimize backend latency.
    Research Gap: Previous models lack single-flight protection.
    Methodology: We implement singleton and locks using Python.
    Literature Review: Several studies highlight thread contention.
    Evaluation: Benchmark before and after.
    """ * 15
    res = await client.post(f"{BASE_URL}/proposals/{proposal_id}/versions", json={
        "original_filename": "bench.pdf",
        "source_type": "pdf",
        "extracted_text": valid_text
    })
    version_id = res.json()["version_id"]
    
    return student_id, proposal_id, version_id

async def time_analysis(client, version_id, label="Single"):
    start = time.time()
    res = await client.post(f"{BASE_URL}/versions/{version_id}/analyze")
    duration = time.time() - start
    if res.status_code != 201:
        print(f"[{label}] Analysis failed: {res.status_code} {res.text}")
    else:
        print(f"[{label}] Analysis finished in {duration:.3f} seconds (Status: {res.status_code})")
    return duration

async def main():
    async with httpx.AsyncClient(timeout=60.0) as client:
        print("Running Setup...")
        student_id, proposal_id, v1_id = await create_setup(client)
        print(f"Created Version 1: {v1_id}")
        
        print("\n--- A. One Isolated Analysis Request ---")
        await time_analysis(client, v1_id, "Isolated")
        
        print("\n--- B. Two Simultaneous Analysis Requests ---")
        _, _, v2_id = await create_setup(client)
        _, _, v3_id = await create_setup(client)
        await asyncio.gather(
            time_analysis(client, v2_id, "Concurrent-1"),
            time_analysis(client, v3_id, "Concurrent-2")
        )

        print("\n--- C. Two Simultaneous Identical Analysis Requests (Testing Deduplication) ---")
        _, _, v4_id = await create_setup(client)
        await asyncio.gather(
            time_analysis(client, v4_id, "Identical-1"),
            time_analysis(client, v4_id, "Identical-2")
        )
        
        print("\nBenchmark complete.")

if __name__ == "__main__":
    asyncio.run(main())
