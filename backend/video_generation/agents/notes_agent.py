import os
import google.generativeai as genai
from backend.video_generation.models import VideoJob, JobStatus

class NotesGeneratorAgent:
    def __init__(self):
        # Assumes GOOGLE_API_KEY is already set in your environment
        self.model = genai.GenerativeModel('gemini-3.5-flash-lite')

    def run(self, job: VideoJob) -> VideoJob:
        job.step = "notes_generator"
        job.progress_percentage = 50

        print(f"[NotesGeneratorAgent] Synthesizing notes for job {job.job_id}")

        prompt = f"""
        You are an expert tutor. The student has uploaded a document and requested structured study notes.
        
        STUDENT INSTRUCTION/EMPHASIS:
        {job.user_prompt}
        {job.emphasis_note or "None"}
        
        EXTRACTED DOCUMENT TEXT (Targeted Pages):
        {job.document_text}
        
        Synthesize a comprehensive, structured study guide based ONLY on the provided text.
        Format the output entirely in standard Markdown (using ## Headings, **bold text**, and bullet points).
        Include key definitions and worked examples if they appear in the text.
        """

        try:
            response = self.model.generate_content(prompt)
            markdown_content = response.text
            
            # Save the notes to the local filesystem
            output_filename = f"Notes_{job.job_id}.md"
            output_path = os.path.join("storage_data", "latex_exports", output_filename)
            
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(markdown_content)
                
            print(f"[NotesGeneratorAgent] Saved notes to {output_path}")
            
            # Repurposing video_path temporarily so the frontend endpoint can return the file path
            job.video_path = output_path        
            job.status = JobStatus.DONE
            
        except Exception as e:
            job.status = JobStatus.ERROR
            job.error_message = f"Failed to generate notes: {str(e)}"

        return job
