from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timedelta
import uuid
import re
import requests
from bs4 import BeautifulSoup

app = FastAPI(title="Scribly API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

scribbles_db = []
custom_categories = []

class Scribble(BaseModel):
    content: str
    tags: Optional[List[str]] = []
    is_confidential: bool = False

class ScribbleResponse(BaseModel):
    id: str
    content: str
    category: str
    tags: List[str]
    is_confidential: bool
    created_at: str
    reminder_date: Optional[str] = None
    url_preview: Optional[dict] = None
    youtube_embed: Optional[str] = None

class CategoryUpdate(BaseModel):
    category: str

class CustomCategory(BaseModel):
    name: str
    icon: Optional[str] = "📁"

def get_url_preview(url: str) -> dict:
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        title = soup.find('title')
        title = title.string if title else url
        
        description = soup.find('meta', attrs={'name': 'description'})
        if description:
            description = description.get('content', '')
        else:
            description = soup.find('meta', attrs={'property': 'og:description'})
            description = description.get('content', '') if description else ''
        
        image = soup.find('meta', attrs={'property': 'og:image'})
        image = image.get('content', '') if image else ''
        
        return {
            'title': title[:200],
            'description': description[:300],
            'image': image,
            'url': url
        }
    except:
        return {'title': url, 'description': '', 'image': '', 'url': url}

def extract_youtube_id(url: str) -> Optional[str]:
    patterns = [
        r'(?:youtube\.com\/watch\?v=|youtu\.be\/)([^&\n?#]+)',
        r'youtube\.com\/embed\/([^&\n?#]+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

def extract_reminder_time(content: str) -> Optional[str]:
    content_lower = content.lower()
    now = datetime.now()
    
    time_match = re.search(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)?', content_lower)
    
    if 'tomorrow' in content_lower:
        base_date = now + timedelta(days=1)
    elif 'today' in content_lower:
        base_date = now
    elif 'next week' in content_lower:
        base_date = now + timedelta(days=7)
    else:
        date_match = re.search(r'(\d{1,2})[/-](\d{1,2})', content_lower)
        if date_match:
            day, month = int(date_match.group(1)), int(date_match.group(2))
            try:
                base_date = datetime(now.year, month, day)
                if base_date < now:
                    base_date = datetime(now.year + 1, month, day)
            except:
                base_date = now
        else:
            base_date = now
    
    if time_match:
        hour = int(time_match.group(1))
        minute = int(time_match.group(2)) if time_match.group(2) else 0
        am_pm = time_match.group(3)
        
        if am_pm == 'pm' and hour != 12:
            hour += 12
        elif am_pm == 'am' and hour == 12:
            hour = 0
        
        reminder_time = base_date.replace(hour=hour, minute=minute, second=0)
        return reminder_time.isoformat()
    
    return None

def categorize_scribble(content: str, tags: List[str], is_confidential: bool) -> tuple:
    if is_confidential:
        return "confidential", None, None, None
    
    content_lower = content.lower()
    url_preview = None
    youtube_embed = None
    reminder_date = None
    
    if "/remindme" in [t.lower() for t in tags] or "remind" in content_lower:
        reminder_date = extract_reminder_time(content)
        return "reminders", None, None, reminder_date
    
    urls = re.findall(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', content)
    if urls:
        url = urls[0]
        
        youtube_id = extract_youtube_id(url)
        if youtube_id:
            url_preview = get_url_preview(url)
            youtube_embed = youtube_id
            return "videos", url_preview, youtube_embed, None
        
        url_preview = get_url_preview(url)
        return "newsletter", url_preview, None, None
    
    if content.startswith('"') or content.startswith("'") or "quote" in content_lower:
        return "quotes", None, None, None
    
    if any(keyword in content_lower for keyword in ["phone", "email", "contact", "@"]):
        return "contacts", None, None, None
    
    if any(keyword in content_lower for keyword in ["idea", "think", "maybe", "what if"]):
        return "ideas", None, None, None
    
    if content.count("\n") > 2 or content.count("-") > 2:
        return "lists", None, None, None
    
    return "uncategorized", None, None, None

@app.get("/")
def root():
    return {"message": "Scribly API is running!", "version": "2.0"}

@app.post("/scribbles", response_model=ScribbleResponse)
def create_scribble(scribble: Scribble):
    scribble_id = str(uuid.uuid4())
    
    category, url_preview, youtube_embed, reminder_date = categorize_scribble(
        scribble.content, 
        scribble.tags, 
        scribble.is_confidential
    )
    
    new_scribble = {
        "id": scribble_id,
        "content": scribble.content,
        "category": category,
        "tags": scribble.tags,
        "is_confidential": scribble.is_confidential,
        "created_at": datetime.now().isoformat(),
        "reminder_date": reminder_date,
        "url_preview": url_preview,
        "youtube_embed": youtube_embed
    }
    
    scribbles_db.append(new_scribble)
    
    return new_scribble

@app.get("/scribbles", response_model=List[ScribbleResponse])
def get_all_scribbles():
    return scribbles_db

@app.get("/scribbles/{scribble_id}", response_model=ScribbleResponse)
def get_scribble(scribble_id: str):
    scribble = next((s for s in scribbles_db if s["id"] == scribble_id), None)
    if not scribble:
        raise HTTPException(status_code=404, detail="Scribble not found")
    return scribble

@app.get("/categories")
def get_categories():
    category_counts = {
        "newsletter": 0,
        "reminders": 0,
        "confidential": 0,
        "quotes": 0,
        "ideas": 0,
        "drafts": 0,
        "videos": 0,
        "links": 0,
        "lists": 0,
        "notes": 0,
        "contacts": 0,
        "uncategorized": 0
    }
    
    for scribble in scribbles_db:
        cat = scribble["category"]
        if cat in category_counts:
            category_counts[cat] += 1
        else:
            category_counts[cat] = 1
    
    return category_counts

@app.get("/categories/{category_name}", response_model=List[ScribbleResponse])
def get_scribbles_by_category(category_name: str):
    filtered = [s for s in scribbles_db if s["category"] == category_name]
    return filtered

@app.post("/categories/custom")
def create_custom_category(category: CustomCategory):
    if category.name.lower() in ["newsletter", "reminders", "confidential", "quotes", "ideas", "drafts", "videos", "links", "lists", "notes", "contacts", "uncategorized"]:
        raise HTTPException(status_code=400, detail="Category name conflicts with built-in category")
    
    custom_categories.append({"name": category.name.lower(), "icon": category.icon})
    return {"message": f"Category '{category.name}' created successfully"}

@app.get("/categories/custom/list")
def get_custom_categories():
    return custom_categories

@app.put("/scribbles/{scribble_id}/category")
def update_scribble_category(scribble_id: str, update: CategoryUpdate):
    scribble = next((s for s in scribbles_db if s["id"] == scribble_id), None)
    if not scribble:
        raise HTTPException(status_code=404, detail="Scribble not found")
    
    scribble["category"] = update.category
    
    return scribble

@app.delete("/scribbles/{scribble_id}")
def delete_scribble(scribble_id: str):
    global scribbles_db
    scribble = next((s for s in scribbles_db if s["id"] == scribble_id), None)
    if not scribble:
        raise HTTPException(status_code=404, detail="Scribble not found")
    
    scribbles_db = [s for s in scribbles_db if s["id"] != scribble_id]
    
    return {"message": "Scribble deleted successfully"}

@app.get("/reminders/upcoming")
def get_upcoming_reminders():
    now = datetime.now()
    upcoming = []
    
    for scribble in scribbles_db:
        if scribble.get("reminder_date"):
            reminder_time = datetime.fromisoformat(scribble["reminder_date"])
            if reminder_time > now:
                upcoming.append(scribble)
    
    upcoming.sort(key=lambda x: x["reminder_date"])
    return upcoming

@app.delete("/scribbles")
def clear_all_scribbles():
    global scribbles_db
    scribbles_db = []
    return {"message": "All scribbles cleared successfully"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)