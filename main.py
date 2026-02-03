from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import List, Optional

from fastapi import (
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.requests import Request
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field, HttpUrl, validator
from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
    func,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker, Session


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "cheb_place.db"
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"
REVIEW_PHOTOS_DIR = STATIC_DIR / "review_photos"
GALLERY_PHOTOS_DIR = STATIC_DIR / "gallery_photos"

STATIC_DIR.mkdir(exist_ok=True)
TEMPLATES_DIR.mkdir(exist_ok=True)
REVIEW_PHOTOS_DIR.mkdir(parents=True, exist_ok=True)
GALLERY_PHOTOS_DIR.mkdir(parents=True, exist_ok=True)


SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH}"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class ReviewStatus(str, Enum):
    pending = "pending"
    approved = "approved"


class Place(Base):
    __tablename__ = "places"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    category = Column(String(100), nullable=False)
    lat = Column(String(50), nullable=False)
    lng = Column(String(50), nullable=False)
    description = Column(Text, nullable=True)

    reviews = relationship("Review", back_populates="place", cascade="all, delete-orphan")


class Review(Base):
    __tablename__ = "reviews"

    id = Column(Integer, primary_key=True, index=True)
    place_id = Column(Integer, ForeignKey("places.id"), nullable=False, index=True)
    author_name = Column(String(255), nullable=True)
    rating = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)
    status = Column(SAEnum(ReviewStatus), default=ReviewStatus.pending, index=True)
    created_at = Column(DateTime, server_default=func.now())

    place = relationship("Place", back_populates="reviews")
    photos = relationship("ReviewPhoto", back_populates="review", cascade="all, delete-orphan")


class ReviewPhoto(Base):
    __tablename__ = "review_photos"

    id = Column(Integer, primary_key=True, index=True)
    review_id = Column(Integer, ForeignKey("reviews.id"), nullable=False, index=True)
    url = Column(String(500), nullable=False)

    review = relationship("Review", back_populates="photos")


class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    date = Column(Date, nullable=False)
    short_info = Column(String(255), nullable=False)
    cover_url = Column(String(500), nullable=True)


class GallerySection(Base):
    __tablename__ = "gallery_sections"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)

    photos = relationship("GalleryPhoto", back_populates="section", cascade="all, delete-orphan")


class GalleryPhoto(Base):
    __tablename__ = "gallery_photos"

    id = Column(Integer, primary_key=True, index=True)
    section_id = Column(Integer, ForeignKey("gallery_sections.id"), nullable=False, index=True)
    url = Column(String(500), nullable=False)

    section = relationship("GallerySection", back_populates="photos")


class Feedback(Base):
    __tablename__ = "feedback"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    contact = Column(String(255), nullable=True)
    message = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class PlaceOut(BaseModel):
    id: int
    name: str
    category: str
    lat: str
    lng: str
    description: Optional[str]

    class Config:
        orm_mode = True


class ReviewPhotoOut(BaseModel):
    id: int
    # Используем простую строку, т.к. в проекте храним относительные пути (/static/...)
    url: str

    class Config:
        orm_mode = True


class ReviewOut(BaseModel):
    id: int
    place_id: int
    author_name: Optional[str]
    rating: int = Field(..., ge=1, le=5)
    text: str
    created_at: datetime
    photos: List[ReviewPhotoOut] = []

    class Config:
        orm_mode = True


class EventOut(BaseModel):
    id: int
    title: str
    date: date
    short_info: str
    cover_url: Optional[HttpUrl]

    class Config:
        orm_mode = True


class GalleryPhotoOut(BaseModel):
    id: int
    # Здесь также удобнее использовать строку, чтобы отдавать относительные URL без строгой валидации
    url: str

    class Config:
        orm_mode = True


class GallerySectionOut(BaseModel):
    id: int
    name: str
    photos: List[GalleryPhotoOut] = []

    class Config:
        orm_mode = True


class FeedbackCreate(BaseModel):
    name: str
    contact: Optional[str]
    message: str


class FeedbackOut(BaseModel):
    id: int
    name: str
    contact: Optional[str]
    message: str
    is_read: bool
    created_at: datetime

    class Config:
        orm_mode = True


class NavItem(BaseModel):
    id: str
    title: str
    path: str
    is_active: bool = False


ADMIN_API_KEY = "change-me-admin-key"
api_key_header = APIKeyHeader(name="X-Admin-Key", auto_error=False)


async def require_admin(api_key: Optional[str] = Depends(api_key_header)) -> None:
    if api_key != ADMIN_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing admin key")


app = FastAPI(
    title="CHEB-PLACE API",
    description="Цифровая карта молодежных пространств Чебоксар",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/", include_in_schema=False)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/index.html", include_in_schema=False)
async def index_html(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/events.html", include_in_schema=False)
async def events_page(request: Request):
    return templates.TemplateResponse("events.html", {"request": request})


@app.get("/gallery.html", include_in_schema=False)
async def gallery_page(request: Request):
    return templates.TemplateResponse("gallery.html", {"request": request})


@app.get("/reviews.html", include_in_schema=False)
async def reviews_page(request: Request):
    return templates.TemplateResponse("reviews.html", {"request": request})


@app.get("/contacts.html", include_in_schema=False)
async def contacts_page(request: Request):
    return templates.TemplateResponse("contacts.html", {"request": request})


@app.get("/map.html", include_in_schema=False)
async def map_page(request: Request):
    return templates.TemplateResponse("map.html", {"request": request})


@app.get("/nav", response_model=List[NavItem], tags=["Навигация"])
async def get_navigation(active: Optional[str] = Query(default=None, description="ID активной страницы")):
    items = [
        NavItem(id="home", title="Главная", path="/", is_active=False),
        NavItem(id="reviews", title="Отзывы", path="#reviews", is_active=False),
        NavItem(id="events", title="Мероприятия", path="#events", is_active=False),
        NavItem(id="gallery", title="Галерея", path="#gallery", is_active=False),
        NavItem(id="contacts", title="Контакты", path="#contacts", is_active=False),
    ]
    if active:
        for item in items:
            if item.id == active:
                item.is_active = True
    return items


@app.get("/places", response_model=List[PlaceOut], tags=["Карта"])
def list_places(db: Session = Depends(get_db)):
    return db.query(Place).all()


@app.post("/reviews", status_code=201, tags=["Отзывы"])
async def create_review(
    place_id: int = Form(..., description="ID локации"),
    author_name: Optional[str] = Form(None, description="Имя автора (необязательно)"),
    rating: int = Form(..., ge=1, le=5, description="Рейтинг от 1 до 5"),
    text: str = Form(..., description="Текст отзыва"),
    files: Optional[List[UploadFile]] = File(None, description="До 5 фотографий"),
    db: Session = Depends(get_db),
):
    place = db.query(Place).filter(Place.id == place_id).first()
    if not place:
        raise HTTPException(status_code=404, detail="Локация не найдена")

    file_list = files or []
    if len(file_list) > 5:
        raise HTTPException(status_code=400, detail="Можно загрузить не более 5 изображений")

    review = Review(
        place_id=place_id,
        author_name=author_name,
        rating=rating,
        text=text,
        status=ReviewStatus.pending,
    )
    db.add(review)
    db.flush()

    for uploaded in file_list:
        ext = Path(uploaded.filename or "").suffix or ".jpg"
        filename = f"review_{review.id}_{datetime.utcnow().timestamp()}{ext}"
        file_path = REVIEW_PHOTOS_DIR / filename
        content = await uploaded.read()
        file_path.write_bytes(content)
        url = f"/static/review_photos/{filename}"
        photo = ReviewPhoto(review_id=review.id, url=url)
        db.add(photo)

    db.commit()
    db.refresh(review)

    return {"id": review.id, "status": review.status}


@app.get("/reviews", response_model=List[ReviewOut], tags=["Отзывы"])
def list_reviews(
    place_id: int = Query(..., description="ID локации"),
    db: Session = Depends(get_db),
):
    query = (
        db.query(Review)
        .filter(Review.place_id == place_id, Review.status == ReviewStatus.approved)
        .order_by(Review.created_at.desc())
    )
    return query.all()


@app.get("/events", response_model=List[EventOut], tags=["Мероприятия"])
def list_events(db: Session = Depends(get_db)):
    return db.query(Event).order_by(Event.date.asc()).all()


@app.get("/gallery", response_model=List[GallerySectionOut], tags=["Галерея"])
def get_gallery(db: Session = Depends(get_db)):
    sections = db.query(GallerySection).all()
    return sections


@app.post("/gallery/upload", tags=["Галерея"])
async def upload_gallery_photo(
    file: UploadFile = File(..., description="Фотография"),
    section_name: str = Form("Общие", description="Название раздела галереи"),
    db: Session = Depends(get_db),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Файл не выбран")

    section = db.query(GallerySection).filter(GallerySection.name == section_name).first()
    if not section:
        section = GallerySection(name=section_name)
        db.add(section)
        db.flush()

    ext = Path(file.filename).suffix or ".jpg"
    filename = f"gallery_{section.id}_{datetime.utcnow().timestamp()}{ext}"
    file_path = GALLERY_PHOTOS_DIR / filename
    content = await file.read()
    file_path.write_bytes(content)
    url = f"/static/gallery_photos/{filename}"

    photo = GalleryPhoto(section_id=section.id, url=url)
    db.add(photo)
    db.commit()
    db.refresh(photo)

    return {
        "id": photo.id,
        "url": photo.url,
        "section_id": section.id,
        "section_name": section.name,
    }


@app.post("/feedback", status_code=201, tags=["Контакты"], response_model=FeedbackOut)
def create_feedback(payload: FeedbackCreate, db: Session = Depends(get_db)):
    feedback = Feedback(
        name=payload.name,
        contact=payload.contact,
        message=payload.message,
        is_read=False,
    )
    db.add(feedback)
    db.commit()
    db.refresh(feedback)
    return feedback


@app.get("/admin/reviews/pending", response_model=List[ReviewOut], tags=["Админка"], dependencies=[Depends(require_admin)])
def admin_list_pending_reviews(db: Session = Depends(get_db)):
    return (
        db.query(Review)
        .filter(Review.status == ReviewStatus.pending)
        .order_by(Review.created_at.desc())
        .all()
    )


@app.post("/admin/reviews/{review_id}/approve", tags=["Админка"], dependencies=[Depends(require_admin)])
def admin_approve_review(review_id: int, db: Session = Depends(get_db)):
    review = db.query(Review).filter(Review.id == review_id).first()
    if not review:
        raise HTTPException(status_code=404, detail="Отзыв не найден")
    review.status = ReviewStatus.approved
    db.commit()
    db.refresh(review)
    return {"id": review.id, "status": review.status}


class PlaceCreate(BaseModel):
    name: str
    category: str
    lat: str
    lng: str
    description: Optional[str]


@app.post("/admin/places", response_model=PlaceOut, tags=["Админка"], dependencies=[Depends(require_admin)])
def admin_create_place(payload: PlaceCreate, db: Session = Depends(get_db)):
    place = Place(**payload.dict())
    db.add(place)
    db.commit()
    db.refresh(place)
    return place


class EventCreate(BaseModel):
    title: str
    date: date
    short_info: str = Field(..., max_length=255)
    cover_url: Optional[str]

    @validator("short_info")
    def validate_short_info(cls, v: str) -> str:
        if "\n" in v or "\r" in v:
            raise ValueError("Краткая информация должна быть в одну строку")
        return v


@app.post("/admin/events", response_model=EventOut, tags=["Админка"], dependencies=[Depends(require_admin)])
def admin_create_event(payload: EventCreate, db: Session = Depends(get_db)):
    event = Event(
        title=payload.title,
        date=payload.date,
        short_info=payload.short_info,
        cover_url=payload.cover_url,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


class GallerySectionCreate(BaseModel):
    name: str


@app.post("/admin/gallery/sections", response_model=GallerySectionOut, tags=["Админка"], dependencies=[Depends(require_admin)])
def admin_create_gallery_section(payload: GallerySectionCreate, db: Session = Depends(get_db)):
    section = GallerySection(name=payload.name)
    db.add(section)
    db.commit()
    db.refresh(section)
    return section


class GalleryPhotoCreate(BaseModel):
    section_id: int
    # Админ-раздел может добавлять любые строки URL (в том числе относительные)
    url: str


@app.post("/admin/gallery/photos", response_model=GalleryPhotoOut, tags=["Админка"], dependencies=[Depends(require_admin)])
def admin_add_gallery_photo(payload: GalleryPhotoCreate, db: Session = Depends(get_db)):
    section = db.query(GallerySection).filter(GallerySection.id == payload.section_id).first()
    if not section:
        raise HTTPException(status_code=404, detail="Раздел галереи не найден")
    photo = GalleryPhoto(section_id=payload.section_id, url=payload.url)
    db.add(photo)
    db.commit()
    db.refresh(photo)
    return photo


@app.get("/admin/events", response_model=List[EventOut], tags=["Админка"], dependencies=[Depends(require_admin)])
def admin_list_events(db: Session = Depends(get_db)):
    """Список всех мероприятий для админ-интерфейса (можно редактировать/удалять)."""
    return db.query(Event).order_by(Event.date.asc()).all()


@app.put("/admin/events/{event_id}", response_model=EventOut, tags=["Админка"], dependencies=[Depends(require_admin)])
def admin_update_event(event_id: int, payload: EventCreate, db: Session = Depends(get_db)):
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Мероприятие не найдено")
    event.title = payload.title
    event.date = payload.date
    event.short_info = payload.short_info
    event.cover_url = payload.cover_url
    db.commit()
    db.refresh(event)
    return event


@app.delete("/admin/events/{event_id}", tags=["Админка"], dependencies=[Depends(require_admin)])
def admin_delete_event(event_id: int, db: Session = Depends(get_db)):
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Мероприятие не найдено")
    db.delete(event)
    db.commit()
    return {"status": "deleted", "id": event_id}


@app.put("/admin/gallery/sections/{section_id}", response_model=GallerySectionOut, tags=["Админка"], dependencies=[Depends(require_admin)])
def admin_rename_gallery_section(section_id: int, payload: GallerySectionCreate, db: Session = Depends(get_db)):
    section = db.query(GallerySection).filter(GallerySection.id == section_id).first()
    if not section:
        raise HTTPException(status_code=404, detail="Раздел галереи не найден")
    section.name = payload.name
    db.commit()
    db.refresh(section)
    return section


@app.delete("/admin/gallery/sections/{section_id}", tags=["Админка"], dependencies=[Depends(require_admin)])
def admin_delete_gallery_section(section_id: int, db: Session = Depends(get_db)):
    section = db.query(GallerySection).filter(GallerySection.id == section_id).first()
    if not section:
        raise HTTPException(status_code=404, detail="Раздел галереи не найден")
    db.delete(section)
    db.commit()
    return {"status": "deleted", "id": section_id}


@app.delete("/admin/gallery/photos/{photo_id}", tags=["Админка"], dependencies=[Depends(require_admin)])
def admin_delete_gallery_photo(photo_id: int, db: Session = Depends(get_db)):
    photo = db.query(GalleryPhoto).filter(GalleryPhoto.id == photo_id).first()
    if not photo:
        raise HTTPException(status_code=404, detail="Фотография не найдена")
    db.delete(photo)
    db.commit()
    return {"status": "deleted", "id": photo_id}


@app.get("/admin/feedback", response_model=List[FeedbackOut], tags=["Админка"], dependencies=[Depends(require_admin)])
def admin_list_feedback(db: Session = Depends(get_db)):
    return db.query(Feedback).order_by(Feedback.created_at.desc()).all()


@app.post("/admin/feedback/{feedback_id}/mark_read", tags=["Админка"], dependencies=[Depends(require_admin)])
def admin_mark_feedback_read(feedback_id: int, db: Session = Depends(get_db)):
    fb = db.query(Feedback).filter(Feedback.id == feedback_id).first()
    if not fb:
        raise HTTPException(status_code=404, detail="Сообщение не найдено")
    fb.is_read = True
    db.commit()
    db.refresh(fb)
    return {"id": fb.id, "is_read": fb.is_read}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)