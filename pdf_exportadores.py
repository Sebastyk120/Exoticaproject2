import os
from google.api_core.client_options import ClientOptions
from google.cloud import documentai
from dotenv import load_dotenv

load_dotenv()

def extract_invoice_number(file_path: str) -> str | None:
    """
    Extracts the invoice number from a PDF or image file using Google Cloud Document AI.
    
    Args:
        file_path: Path to the invoice file (PDF, JPG, PNG, etc.).
        
    Returns:
        The extracted invoice number as a string, or None if not found.
    """
    project_id = os.environ.get("GCP_PROJECT_ID")
    location = os.environ.get("GCP_LOCATION")
    processor_id = os.environ.get("GCP_INVOICE_PROCESSOR_ID")
    
    if not all([project_id, location, processor_id]):
        print("Error: Missing required environment variables (GCP_PROJECT_ID, GCP_LOCATION, GCP_INVOICE_PROCESSOR_ID).")
        return None

    # You must set the api_endpoint if you use a location other than 'us'.
    opts = ClientOptions(api_endpoint=f"{location}-documentai.googleapis.com")
    
    try:
        client = documentai.DocumentProcessorServiceClient(client_options=opts)
    except Exception as e:
        print(f"Error initializing Document AI client: {e}")
        return None

    name = client.processor_path(project_id, location, processor_id)

    # Read the file into memory
    try:
        with open(file_path, "rb") as image:
            image_content = image.read()
    except FileNotFoundError:
        print(f"Error: File not found at {file_path}")
        return None

    # Load Binary Data into Document AI RawDocument Object
    mime_type = "application/pdf" if file_path.lower().endswith(".pdf") else "image/jpeg" # Basic mime type detection
    # Note: For production, use a library like `mimetypes` or `python-magic` for better detection.
    
    raw_document = documentai.RawDocument(content=image_content, mime_type=mime_type)

    # Configure the process request
    request = documentai.ProcessRequest(name=name, raw_document=raw_document)

    try:
        result = client.process_document(request=request)
    except Exception as e:
        print(f"Error processing document: {e}")
        return None

    document = result.document

    # Iterate over entities to find the invoice number
    # The entity type for invoice number in Google Invoice Parser is usually "invoice_id"
    for entity in document.entities:
        # You might need to adjust "invoice_id" based on your specific processor version or schema
        if entity.type_ == "invoice_id":
            return entity.mention_text

    return None

if __name__ == "__main__":
    import sys
    # Example usage:
    # Set your environment variables before running this script.
    # python pdf_exportadores.py [file_path]
    
    print("Document AI Invoice Extraction Test")
    print("-----------------------------------")
    
    if len(sys.argv) > 1:
        test_file = sys.argv[1]
    else:
        test_file = input("Enter the path to an invoice file to test: ").strip()
    
    if test_file:
        invoice_num = extract_invoice_number(test_file)
        if invoice_num:
            print(f"Extracted Invoice Number: {invoice_num}")
        else:
            print("Invoice number not found or extraction failed.")
    else:
        print("No file path provided.")
