from fastapi import FastAPI
from pydantic import BaseModel
from openai import OpenAI
from dotenv import load_dotenv

from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from fastapi.middleware.cors import CORSMiddleware
import os

app = FastAPI()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://ebis-ai-sales-automation-frontend.vercel.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Conversation Memory
conversation_memory = []

# SQLite Database
DATABASE_URL = "sqlite:///./crm.db"

engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()


# Lead Table
class Lead(Base):

    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, index=True)

    company_size = Column(String)
    budget = Column(String)
    timeline = Column(String)
    use_case = Column(String)
    lead_quality = Column(String)


Base.metadata.create_all(bind=engine)

load_dotenv()

client = OpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1"
)

# Request Model
class ChatRequest(BaseModel):
    message: str


@app.get("/")
def home():

    return {
        "message": "EBIS AI Agent Running"
    }


@app.post("/chat")
async def chat(request: ChatRequest):

    user_message = request.message

    # SAVE USER MESSAGE TO MEMORY
    conversation_memory.append({
        "role": "user",
        "content": user_message
    })

    # SINGLE AI CALL
    response = client.chat.completions.create(
model="llama-3.1-8b-instant",

        messages=[

            {
                "role": "system",
                "content": """
                You are an AI sales qualification assistant for EBIS Bank.

                Your goal:
                - qualify sales leads
                - understand customer requirements
                - collect:
                    1. company size
                    2. budget
                    3. timeline
                    4. use case

                Rules:
                - sound like ChatGPT
                - keep responses short
                - ask one question at a time
                - continue conversation naturally
                - avoid greetings
                - avoid sign-offs
                """
            },

            *conversation_memory

        ]

    )

    # AI REPLY
    ai_reply = response.choices[0].message.content

    # SAVE AI RESPONSE TO MEMORY
    conversation_memory.append({
        "role": "assistant",
        "content": ai_reply
    })

    return {
        "reply": ai_reply
    }


@app.get("/leads")
def get_leads():

    db = SessionLocal()

    leads = db.query(Lead).all()

    result = []

    for lead in leads:

        result.append({

            "id": lead.id,
            "company_size": lead.company_size,
            "budget": lead.budget,
            "timeline": lead.timeline,
            "use_case": lead.use_case,
            "lead_quality": lead.lead_quality

        })

    db.close()

    return result