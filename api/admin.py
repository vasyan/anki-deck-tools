from datetime import datetime
import json
from fastapi import APIRouter, HTTPException, Request, Depends
from typing import Dict

from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from database.manager import DatabaseManager
from models.database import AnkiCard, LearningContent, ContentFragment
from models.schemas import ContentFragmentInput
from database.manager import DatabaseManager
from fastapi.responses import HTMLResponse
import logging
import asyncio
import uuid
from pathlib import Path
from services.example_generator import ExampleGeneratorService
from services.fragment_manager import FragmentManager
from services.learning_content_service import extract_object_data, format_operation_result
from workflows.anki_builder import AnkiBuilder
from fastapi import Form
from pydantic import ValidationError

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

templates = Jinja2Templates(directory="templates")

db_manager = DatabaseManager()

router = APIRouter()

task_storage: Dict[str, Dict] = {}

class GenerateExampleOptions:
    def __init__(
        self,
        columns: str = Form(...),
        instructions_file: str = Form(...),
        limit: int = Form(5),
        learning_content_id: int | None = Form(None),
        parallel: bool = Form(False),
        dry_run: bool = Form(False),
    ):
        self.columns = columns
        self.instructions_file = instructions_file
        self.limit = limit
        self.learning_content_id = learning_content_id
        self.parallel = parallel
        self.dry_run = dry_run

@router.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    """Main admin dashboard"""
    return templates.TemplateResponse("admin/dashboard.html", {"request": request})


@router.post("/admin/example/preview")
async def preview_example_generation(
    options: GenerateExampleOptions = Depends(GenerateExampleOptions)
):
    logger.debug(f"/admin/example/preview: previewing example generation {options.learning_content_id}")
    """Preview example generation with sample cards"""
    try:
        # Validate instruction file exists
        instructions_path = Path(options.instructions_file)
        if not instructions_path.exists():
            raise HTTPException(status_code=400, detail="Instruction file not found")

        # Read instruction template
        with open(instructions_path, 'r', encoding='utf-8') as f:
            template_str = f.read()

        # Parse columns
        columns_list = [c.strip() for c in options.columns.split(',')]

        # Get sample cards
        with db_manager.get_session() as session:
            query = session.query(LearningContent)

            # If learning_content_id is specified, only get that specific learning content
            if options.learning_content_id:
                query = query.filter(LearningContent.id == options.learning_content_id)
                sample_learning_contents = query.all()
            else:
                # Get first random learning content
                sample_learning_contents = query.order_by(func.random()).limit(options.limit).all()

        if not sample_learning_contents:
            return {"preview_results": [], "message": "No learning contents available for preview"}

        # Generate preview examples
        example_service = ExampleGeneratorService()
        preview_results = []

        for learning_content in sample_learning_contents:
            try:
                # Get card data for specified columns
                learning_content_data = {}
                for col in columns_list:
                    if hasattr(learning_content, col):
                        learning_content_data[col] = getattr(learning_content, col)
                    else:
                        learning_content_data[col] = None

                # Generate example
                generated_example = example_service.generate_example_from_learning_content(learning_content_data, template_str)

                preview_results.append({
                    "learning_content_id": learning_content.id,
                    "learning_content_data": learning_content_data,
                    "generated_example": generated_example,
                    "status": "success"
                })

            except Exception as e:
                preview_results.append({
                    "learning_content_id": learning_content.id,
                    "learning_content_data": learning_content_data,
                    "generated_example": None,
                    "error": str(e),
                    "status": "error"
                })

        return {
            "preview_results": preview_results,
            "total_learning_contents": len(sample_learning_contents),
            "template_trimmed": template_str[:200] + "..." if len(template_str) > 200 else template_str,
            "template": template_str
        }

    except Exception as e:
        logger.error(f"Error previewing example generation: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/admin/example/start")
async def start_example_generation(
    options: GenerateExampleOptions = Depends(GenerateExampleOptions)
):
    logger.debug(f"/admin/example/start: starting example generation task {options.learning_content_id}")
    """Start example generation process"""
    try:
        # Validate instruction file exists
        instructions_path = Path(options.instructions_file)
        if not instructions_path.exists():
            raise HTTPException(status_code=400, detail="Instruction file not found")

        # Create task
        task_id = str(uuid.uuid4())
        task_storage[task_id] = {
            "task_id": task_id,
            "status": "started",
            "progress": 0,
            "message": "🤖 Starting example generation...",
            "columns": options.columns,
            "instructions_file": options.instructions_file,
            "limit": options.limit,
            "parallel": options.parallel,
            "dry_run": options.dry_run,
            "learning_content_id": options.learning_content_id,
            "result": None
        }

        # Start background task
        asyncio.create_task(run_example_generation_task(task_id))

        return {
            "task_id": task_id,
            "status": "started",
            "message": "Example generation started"
        }

    except Exception as e:
        logger.error(f"Error starting example generation: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/admin/example/status/{task_id}")
async def get_example_generation_status(task_id: str):
    """Get status of example generation task"""
    task = task_storage.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return {
        "task_id": task_id,
        "status": task["status"],
        "progress": task["progress"],
        "message": task["message"],
        "result": task.get("result")
    }

@router.get("/admin/example/results/{task_id}")
async def get_example_generation_results(task_id: str):
    """Get results of completed example generation task"""
    task = task_storage.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task["status"] != "completed":
        raise HTTPException(status_code=400, detail="Task not completed")

    return task.get("result", {})

@router.get("/admin/example", response_class=HTMLResponse)
async def admin_example(request: Request):
    """Example generation admin page"""
    return templates.TemplateResponse("admin/example_form.html", {"request": request})

@router.get("/admin/fragments", response_class=HTMLResponse)
async def admin_fragments(request: Request):
    """Fragment management admin page"""
    return templates.TemplateResponse("admin/fragments.html", {"request": request})

@router.get("/admin/learning-content", response_class=HTMLResponse)
async def admin_learning_content(request: Request):
    """Learning content management admin page"""
    return templates.TemplateResponse("admin/learning_content.html", {"request": request})

@router.get("/admin/learning-content/{content_id}/detail", response_class=HTMLResponse)
async def admin_learning_content_detail(request: Request, content_id: int):
    """Learning content detail page"""
    return templates.TemplateResponse("admin/learning_content_detail.html", {"request": request})

@router.get("/admin/fragments/{fragment_id}/detail", response_class=HTMLResponse)
async def admin_fragment_detail(request: Request, fragment_id: int):
    """Fragment detail page"""
    return templates.TemplateResponse("admin/fragment_detail.html", {"request": request})

@router.get("/admin/example/instructions")
async def list_instruction_files():
    """List available instruction template files"""
    try:
        instructions_dir = Path("instructions")
        if not instructions_dir.exists():
            return {"files": []}

        files = []
        for file_path in instructions_dir.glob("*.txt"):
            files.append({
                "name": file_path.name,
                "path": str(file_path),
                "size": file_path.stat().st_size
            })

        return {"files": files}
    except Exception as e:
        logger.error(f"Error listing instruction files: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/admin/example/decks")
async def list_available_decks():
    """List available decks for selection"""
    try:
        with db_manager.get_session() as session:
            # Get distinct deck names from the database
            decks = session.query(AnkiCard.deck_name).distinct().all()
            deck_names = [deck[0] for deck in decks if deck[0]]  # Filter out None values

            return {
                "decks": sorted(deck_names),
                "total_count": len(deck_names)
            }
    except Exception as e:
        logger.error(f"Error listing available decks: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def run_example_generation_task(task_id: str):
    """Background task for example generation"""
    task = task_storage[task_id]

    try:
        # Update status
        task["status"] = "running"
        task["progress"] = 10
        task["message"] = "📊 Loading cards and template..."

        # Read instruction template
        with open(task["instructions_file"], 'r', encoding='utf-8') as f:
            template_str = f.read()

        # Parse columns
        columns_list = [c.strip() for c in task["columns"].split(',')]

        # Get cards to process
        with db_manager.get_session() as session:
            query = session.query(LearningContent)

            # If learning_content_id is specified, only process that specific learning content
            if task["learning_content_id"]:
                query = query.filter(LearningContent.id == task["learning_content_id"])
                learning_contents = query.all()
            else:
                if task["limit"]:
                    query = query.limit(task["limit"])

                learning_contents = query.all()

        if not learning_contents:
            task["status"] = "completed"
            task["progress"] = 100
            task["message"] = "✅ No learning contents found for processing"
            task["result"] = {
                "processed_learning_contents": 0,
                "successful": 0,
                "failed": 0,
                "total_time": 0,
                "dry_run": task["dry_run"]
            }
            return

        # Update progress
        task["progress"] = 20
        if task["learning_content_id"]:
            task["message"] = f"🔄 Processing learning content ID {task['learning_content_id']}..."
        else:
            task["message"] = f"🔄 Processing {len(learning_contents)} learning contents..."

        # Initialize example service
        example_service = ExampleGeneratorService()

        # Process learning contents
        successful = 0
        failed = 0
        failed_learning_contents = []
        dry_run_results = []

        import time
        start_time = time.time()

        if task["parallel"]:
            # Parallel processing
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                futures = []
                for learning_content in learning_contents:
                    future = executor.submit(process_single_learning_content, learning_content, columns_list, template_str, example_service, task["dry_run"])
                    futures.append((learning_content, future))

                for i, (learning_content, future) in enumerate(futures):
                    logger.debug(f" %%%%%%% processing learning_content: {learning_content.id}")
                    try:
                        result = future.result()
                        if result["success"]:
                            successful += 1
                            if task["dry_run"]:
                                dry_run_results.append({
                                    "learning_content_id": learning_content.id,
                                    "learning_content_data": result["learning_content_data"],
                                    "generated_example": result["generated_example"],
                                    "content_fragment_id": result["content_fragment_id"]
                                })
                        else:
                            failed += 1
                            failed_learning_contents.append({
                                "learning_content_id": learning_content.id,
                                "learning_content_data": result["learning_content_data"],
                                "error": result["error"]
                            })
                    except Exception as e:
                        failed += 1
                        failed_learning_contents.append({
                            "learning_content_id": learning_content.id,
                            "learning_content_data": result["learning_content_data"],
                            "error": str(e)
                        })

                    # Update progress
                    progress = 20 + int(((i + 1) / len(learning_contents)) * 70)
                    task["progress"] = progress
                    task["message"] = f"🔄 Processed {i + 1} of {len(learning_contents)} learning contents..."
        else:
            # Sequential processing
            for i, learning_content in enumerate(learning_contents):
                try:
                    result = process_single_learning_content(learning_content, columns_list, template_str, example_service, task["dry_run"])
                    if result["success"]:
                        successful += 1
                        if task["dry_run"]:
                            dry_run_results.append({
                                "learning_content_id": learning_content.id,
                                "learning_content_data": result["learning_content_data"],
                                "generated_example": result["generated_example"],
                                "content_fragment_id": result["content_fragment_id"]
                            })
                    else:
                        failed += 1
                        failed_learning_contents.append({
                            "learning_content_id": learning_content.id,
                            "learning_content_data": result["learning_content_data"],
                            "error": result["error"]
                        })
                except Exception as e:
                    failed += 1
                    failed_learning_contents.append({
                        "learning_content_id": learning_content.id,
                        "learning_content_data": result["learning_content_data"],
                        "error": str(e)
                    })

                # Update progress
                progress = 20 + int(((i + 1) / len(learning_contents)) * 70)
                task["progress"] = progress
                task["message"] = f"🔄 Processed {i + 1} of {len(learning_contents)} learning contents..."

        # Final update
        end_time = time.time()
        processing_time = end_time - start_time

        task["status"] = "completed"
        task["progress"] = 100
        task["message"] = f"✅ Example generation completed! Success: {successful}, Failed: {failed}"
        task["result"] = {
            "processed_learning_contents": len(learning_contents),
            "successful": successful,
            "failed": failed,
            "failed_learning_contents": failed_learning_contents,
            "processing_time": processing_time,
            "dry_run": task["dry_run"],
            "dry_run_results": dry_run_results if task["dry_run"] else []
        }

        logger.info(f"Example generation completed. Task: {task_id}, Success: {successful}, Failed: {failed}")

    except Exception as e:
        task["status"] = "error"
        task["progress"] = -1
        task["message"] = f"❌ Error: {str(e)}"
        logger.error(f"Example generation task failed: {e}")
        logger.debug(f"forr task: {task}")

def process_single_learning_content(learning_content, columns_list, template_str, example_service, dry_run):
    logger.debug(f"/admin/example/process_single_learning_content: processing single learning content {learning_content.id}")
    """Process a single learning content for example generation"""
    try:
        # Extract learning content data using utility function
        learning_content_data = extract_object_data(learning_content, columns_list)
        print(learning_content_data)

        # we getting JSON formatted list of examples and need to parse it
        generated_examples = json.loads(example_service.generate_example(learning_content_data, template_str))

        # logger.debug(f"generated_examples: {generated_examples}")
        # logger.debug(f"generated_examples type: {type(generated_examples)}")
        # logger.debug(f"generated_examples as json: {json.loads(generated_examples)}")
        # mapped_generated_examples = []
        # try:
        #   mapped_generated_examples = [{
        #       'body_text': generated_example.get('body_text', ''),
        #       'fragment_type': generated_example.get('type', ''),
        #       'native_text': generated_example.get('native_text', ''),
        #       'ipa': generated_example.get('ipa', ''),
        #       'extra': generated_example.get('extra', '')
        #   } for generated_example in json.loads(generated_examples)]
        # except Exception as e:
        #     logger.error(f"/admin/example/process_single_learning_content: error parsing generated examples: {e}")

        # logger.debug(f"mapped generated_examples: {mapped_generated_examples}")

        # content_fragments = []
        # try:
        #   content_fragments = [
        #       ContentFragment(
        #           learning_content_id=learning_content.id,
        #           body_text=generated_example['body_text'],
        #           fragment_type=generated_example['fragment_type'],
        #           native_text=generated_example['native_text'],
        #           ipa=generated_example['ipa'],
        #           extra=generated_example['extra']
        #       ) for generated_example in mapped_generated_examples
        #   ]
        # except Exception as e:
        #     logger.error(f" ++++++++++++++ parsing generated examples: {e}")

        logger.debug(f"========== generated_examples: {generated_examples}")

        created_fragment_ids = []  # collect ids of inserted fragments

        for content_fragment in generated_examples:
            if not dry_run:
                logger.debug(f" ++++++++++++++ content_fragment: {content_fragment, learning_content.id}")
                logger.debug(f"type of content_fragment: {type(content_fragment)}")
                # Validate incoming data with Pydantic.
                try:
                    validated = ContentFragmentInput(
                        learning_content_id=learning_content.id,
                        **content_fragment  # unpack dict keys to model fields
                    )
                except ValidationError as e:
                    # Skip invalid fragments but keep processing others
                    logger.error(f"Invalid fragment data for learning_content {learning_content.id}: {e}")
                    continue

                fragment_manager = FragmentManager()
                try:
                  fid = fragment_manager.create_fragment(
                      **validated.model_dump(exclude_none=True),  # unpack validated data
                      metadata={
                          'source_columns': columns_list,
                          'template_used': template_str[:100] + '...' if len(template_str) > 100 else template_str
                      },
                  )
                  created_fragment_ids.append(fid)
                except Exception as e:
                    logger.error(f" !!!!!!!!!!! error creating fragment: {e}")
                    continue


        # Use standard result formatting
        return format_operation_result(
            success=True,
            data={
                "learning_content_data": learning_content_data,
                "content_fragments": generated_examples,
                "content_fragment_ids": created_fragment_ids
            }
        )

    except Exception as e:
        return format_operation_result(
            success=False,
            data={"learning_content_data": learning_content_data},
            error=str(e)
        )

@router.get("/admin/test-anki-builder")
async def render_card(request: Request):
    anki_builder = AnkiBuilder()
    materials = await anki_builder.get_materials(52)

    return {
        "message": "Card rendered",
        "materials": materials
    }
