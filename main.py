from fastapi import FastAPI, Path, Header, HTTPException, Body, status
from pydantic import BaseModel
import sqlite3
from typing import Optional

app = FastAPI()

DB_NAME = "academy.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY
        );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS courses (
            course_id TEXT PRIMARY KEY
        );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS enrollments (
            user_id TEXT,
            course_id TEXT,
            PRIMARY KEY (user_id, course_id)
        );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS lessons (
            lesson_id TEXT,
            course_id TEXT,
            PRIMARY KEY (lesson_id, course_id)
        );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS lesson_completion (
            user_id TEXT,
            course_id TEXT,
            lesson_id TEXT,
            PRIMARY KEY (user_id, course_id, lesson_id)
        );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ratings (
            user_id TEXT,
            course_id TEXT,
            rating INTEGER,
            PRIMARY KEY (user_id, course_id)
        );
    """)

    conn.commit()
    conn.close()


@app.on_event("startup")
def startup_event():
    init_db()

class RatingIn(BaseModel):
    rating: int


def db():
    return sqlite3.connect(DB_NAME)


def is_enrolled(user_id, course_id):
    conn = db()
    res = conn.execute(
        "SELECT 1 FROM enrollments WHERE user_id=? AND course_id=?",
        (user_id, course_id)
    ).fetchone()
    conn.close()
    return res is not None

@app.post("/courses/{course_id}/enroll")
def enroll_user(
    course_id: str = Path(...),
    x_user_id: str = Header(..., alias="X-User-Id")
):
    conn = db()
    try:
        conn.execute("INSERT INTO users (user_id) VALUES (?) ON CONFLICT DO NOTHING", (x_user_id,))
        conn.execute("INSERT INTO courses (course_id) VALUES (?) ON CONFLICT DO NOTHING", (course_id,))
        conn.execute(
            "INSERT INTO enrollments (user_id, course_id) VALUES (?, ?)",
            (x_user_id, course_id)
        )
        conn.commit()
    except sqlite3.IntegrityError:
        return {"message": "User already enrolled"}
    finally:
        conn.close()

    return {"message": "Enrolled successfully"}

@app.post("/courses/{course_id}/lessons/{lesson_id}/complete")
def complete_lesson(
    course_id: str = Path(...),
    lesson_id: str = Path(...),
    x_user_id: str = Header(..., alias="X-User-Id")
):
    if not is_enrolled(x_user_id, course_id):
        raise HTTPException(status_code=403, detail="User not enrolled")

    conn = db()
    conn.execute("INSERT INTO lessons (lesson_id, course_id) VALUES (?, ?) ON CONFLICT DO NOTHING",
                 (lesson_id, course_id))
    conn.execute("""
        INSERT INTO lesson_completion (user_id, course_id, lesson_id)
        VALUES (?, ?, ?)
        ON CONFLICT DO NOTHING
    """, (x_user_id, course_id, lesson_id))
    conn.commit()
    conn.close()

    return {"message": "Lesson completion recorded"}

@app.get("/users/{user_id}/courses/{course_id}/progress")
def get_progress(
    user_id: str = Path(...),
    course_id: str = Path(...)
):
    conn = db()

    total_lessons = conn.execute(
        "SELECT COUNT(*) FROM lessons WHERE course_id=?", (course_id,)
    ).fetchone()[0]

    completed = conn.execute(
        "SELECT COUNT(*) FROM lesson_completion WHERE user_id=? AND course_id=?",
        (user_id, course_id)
    ).fetchone()[0]

    conn.close()

    progress = 0 if total_lessons == 0 else (completed / total_lessons) * 100

    return {"completed": completed, "total": total_lessons, "progress": progress}

@app.post("/courses/{course_id}/rating")
def rate_course(
    course_id: str = Path(...),
    rating_in: RatingIn = Body(...),
    x_user_id: str = Header(..., alias="X-User-Id"),
):
    if not is_enrolled(x_user_id, course_id):
        raise HTTPException(status_code=403, detail="User not enrolled, cannot rate")

    conn = db()
    conn.execute("""
        INSERT INTO ratings (user_id, course_id, rating)
        VALUES (?, ?, ?)
        ON CONFLICT(user_id, course_id)
        DO UPDATE SET rating=excluded.rating
    """, (x_user_id, course_id, rating_in.rating))
    conn.commit()
    conn.close()

    return {"message": "Rating submitted"}

@app.get("/courses/{course_id}/rating")
def get_rating(course_id: str = Path(...)):
    conn = db()
    data = conn.execute(
        "SELECT AVG(rating), COUNT(*) FROM ratings WHERE course_id=?",
        (course_id,)
    ).fetchone()
    conn.close()

    avg_rating, count = data
    return {"average_rating": avg_rating or 0, "total_ratings": count}

@app.get("/courses/{course_id}/lessons")
def get_lessons(
    course_id: str = Path(...),
    x_user_id: str = Header(..., alias="X-User-Id")
):
    if not is_enrolled(x_user_id, course_id):
        raise HTTPException(status_code=403, detail="User not enrolled")

    conn = db()
    lessons = conn.execute(
        "SELECT lesson_id FROM lessons WHERE course_id=?",
        (course_id,)
    ).fetchall()
    conn.close()

    return {"lessons": [row[0] for row in lessons]}