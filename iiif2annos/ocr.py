#!/usr/bin/env python

from PIL import Image
import requests
from io import BytesIO
import pytesseract
from pytesseract import Output
import argparse
import json

def canvases(manifest, sequence=0):
    if 'type' in manifest:
        return manifest['items']
    else:
        return manifest["sequences"][sequence]["canvases"]

def get_service(canvas):
    if 'id' in canvas:
        return canvas['items'][0]['items'][0]['body']['service'] 
    else:     
        return canvas['images'][0]['resource']['service']
     

def buildIIIFImage(service):
     if '@id' in service:
        return f"{service['@id']}/full/full/0/default.jpg"
     else:     
        return f"{service[0]['id']}/full/max/0/default.jpg"

def buildAnno(canvas, ident, x, y, width, height, content):
    if 'id' in canvas:
        return {
            "id": ident,
            "type": "Annotation",
            "motivation": "commenting",
            "body": {
                "type": "TextualBody",
                "format": "text/plain",
                "value": content
            },
            "target": f"{canvas['id']}#xywh={x},{y},{width},{height}"
        }
    else:
        return  {
            "@id": ident,
            "@type": "oa:Annotation",
            "motivation": "commenting",
            "resource": {
                "@type": "cnt:ContentAsText",
                "format": "text/plain",
                "chars": content
            },
            "on": f"{canvas['@id']}#xywh={x},{y},{width},{height}"
        }   

def mkannotations(canvas, ident, annotations):
    if 'id' in canvas:
        return  {
            "@context": "http://iiif.io/api/presentation/3/context.json",
            "id": ident,
            "type": "AnnotationPage",
            "items": annotations
        }       
    else:
        return {
            "@context": "http://iiif.io/api/presentation/3/context.json",
            "@id": ident,
            "@type": "AnnotationList",
            "resources": annotations
        }    
def addAnnotations(canvas, ident):
    if 'id' in canvas:
        canvas["annotations"] = [
            {
                "id": ident,
                "type": "AnnotationPage",
                "label": "Annotations generated by Tesseract"
            }
        ]   
    else:
        canvas["otherContent"] = [
            {
                "@id": ident,
                "@type": "sc:AnnotationList",
                "label": "Annotations generated by Tesseract"
            }
        ]  
def ocr(anno_uri, outputDir, manifestURI, lang=None, confidence=False):
    # Data is either a string or parsed JSON
    print (f'Loading: {manifestURI}')
    manifest = requests.get(manifestURI).json()

    canvasNo = 0
    for canvas in canvases(manifest):
        service = get_service(canvas)

        url = buildIIIFImage(service)
        print (f'Downloading {url}')
        response = requests.get(url)
        img = Image.open(BytesIO(response.content))

        print ('Running OCR')
        if lang:
            data = pytesseract.image_to_data(img, output_type=Output.DICT, lang=lang)
        else:
            data = pytesseract.image_to_data(img, output_type=Output.DICT)
        annos = []
        annoNo = 0
        for i in range(len(data['text'])):
            if data['conf'][i] >= 0:
                (x, y, width, height) = (data['left'][i], data['top'][i], data['width'][i], data['height'][i])
                ident = f"{anno_uri}/{canvasNo}/annotation/{annoNo}"
                if confidence:
                    content = f"Confidence: {data['conf'][i]}: {data['text'][i]}"
                else:    
                    content = f"{data['text'][i]}"

                annos.append(buildAnno(canvas, ident, x, y, width, height, content))

                annoNo += 1

        annotationsID = f"{anno_uri}/{canvasNo}.json"
        annotations = mkannotations(canvas,annotationsID, annos)
        
        print (f"Saving {outputDir}/{canvasNo}.json")
        with open(f'{outputDir}/{canvasNo}.json', 'w') as f:
            json.dump(annotations, f, indent=4)

        addAnnotations(canvas, annotationsID)
        canvasNo += 1

    with open(f'{outputDir}/manifest.json', 'w') as f:
        json.dump(manifest, f, indent=4)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
                    prog='ocr.py',
                    description='Read a manifest, OCR all the pages then adds the results as annotation lists')

    parser.add_argument('manifest', help="URL to Manifest file")
    parser.add_argument('output', help='Output directory for annotation lists')
    parser.add_argument('--base-output-uri', dest='outputURI', default='http://localhost/annos', help='Output URI for annotations')                
    parser.add_argument('--lang', dest='lang', default=None, help='Language to pass to the OCR engine see: https://tesseract-ocr.github.io/tessdoc/Data-Files-in-different-versions.html')                
    parser.add_argument('-c', '--confidence', dest='confidence', action='store_true', default=False, help='Include OCR confidence value in text of the annotation? ')
    args = parser.parse_args()

    ocr(args.outputURI, args.output, args.manifest, args.lang, args.confidence)