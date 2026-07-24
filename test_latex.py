import requests
import base64
import time

def test_latex():
    # A tiny 1x1 transparent PNG just to trigger the pipeline
    dummy_image = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
    
    print("Submitting to local backend...")
    resp = requests.post(
        "http://127.0.0.1:8000/generate_latex",
        data={"image_b64": dummy_image, "template_type": "Homework"}
    )
    
    if resp.status_code != 200:
        print(f"Backend failed: {resp.text}")
        return
        
    job_id = resp.json().get("job_id")
    print(f"Job ID: {job_id}. Waiting for completion...")
    
    for i in range(100):
        time.sleep(2)
        r = requests.get(f"http://127.0.0.1:8000/latex_status/{job_id}")
        data = r.json()
        print(f"Status: {data.get('status')} | Step: {data.get('step')} | Error: {data.get('error_message')}")
        
        if data.get("status") in ["completed", "done", "success"]:
            print("SUCCESS! PDF is ready.")
            break
        elif data.get("status") == "error":
            print("FAILED in backend!")
            break

if __name__ == "__main__":
    test_latex()
