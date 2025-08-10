from docling.document_converter import DocumentConverter
import torch

def extract_pdf(dir="https://arxiv.org/pdf/2408.09869"):
    source = dir
    converter = DocumentConverter()
    result = converter.convert(source)
    try:
        torch.cuda.empty_cache()
    except:
        pass
    return result.document.export_to_markdown()