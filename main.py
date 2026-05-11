from fastapi import FastAPI
from pydantic import BaseModel
from openai import OpenAI
from dotenv import load_dotenv

from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from fastapi.middleware.cors import CORSMiddleware

import os
import json
import re

app = FastAPI()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://ebis-ai-sales-automation-frontend.vercel.app"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# CONVERSATION MEMORY
conversation_memory = []

# DATABASE
DATABASE_URL = "sqlite:///./crm.db"

engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()

# LEAD TABLE
class Lead(Base):

    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, index=True)

    company_size = Column(String)
    budget = Column(String)
    timeline = Column(String)
    use_case = Column(String)
    lead_quality = Column(String)

Base.metadata.create_all(bind=engine)

# LOAD ENV VARIABLES
load_dotenv()

# GROQ CLIENT
client = OpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1"
)

# REQUEST MODEL
class ChatRequest(BaseModel):
    message: str


# HOME ROUTE
@app.get("/")
def home():

    return {
        "message": "EBIS AI Agent Running"
    }


# HEALTH CHECK
@app.get("/health")
def health():

    return {
        "status": "ok"
    }


# CHAT ENDPOINT
@app.post("/chat")
async def chat(request: ChatRequest):

    user_message = request.message

    # SAVE USER MESSAGE
    conversation_memory.append({
        "role": "user",
        "content": user_message
    })

    # AI CONVERSATION RESPONSE
    response = client.chat.completions.create(

        model="llama-3.1-8b-instant",

        messages=[

            {
                "role": "system",
                "content": """
                You are an AI sales qualification assistant for EBIS Bank.

                Your goals:
                - qualify business leads
                - understand customer requirements
                - collect:
                    1. company size
                    2. budget
                    3. timeline
                    4. use case

                Rules:
                - sound modern and conversational
                - keep responses short
                - ask one question at a time
                - avoid greetings
                - avoid sign-offs
                - continue naturally
                - stop asking once all information is collected
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

    # EXTRACT LEAD INFORMATION
    extract_response = client.chat.completions.create(

        model="llama-3.1-8b-instant",

        messages=[

            {
                "role": "system",
                "content": """
                You are a JSON extraction engine.

                Return ONLY valid raw JSON.

                No markdown.
                No explanations.
                No extra text.

                Format:

                {
                  "company_size":"",
                  "budget":"",
                  "timeline":"",
                  "use_case":"",
                  "lead_quality":""
                }

                Rules:
                - lead_quality must be:
                  High / Medium / Low
                - missing values should be empty strings
                """
            },

            {
                "role": "user",
                "content": user_message
            }

        ]

    )

    extracted_text = extract_response.choices[0].message.content

    print(extracted_text)

    lead_data = {}

    # PARSE JSON
    try:

        json_match = re.search(
            r'\{.*\}',
            extracted_text,
            re.DOTALL
        )

        if json_match:

            lead_data = json.loads(
                json_match.group()
            )

    except Exception as e:

        print(e)

    # REQUIRED FIELDS
    required_fields = [
        "company_size",
        "budget",
        "timeline",
        "use_case"
    ]

    # CHECK COMPLETION
    is_complete = all(
        lead_data.get(field)
        for field in required_fields
    )

    # SAVE ONLY COMPLETE LEADS
    if is_complete:

        db = SessionLocal()

        new_lead = Lead(

            company_size=lead_data.get(
                "company_size",
                ""
            ),

            budget=lead_data.get(
                "budget",
                ""
            ),

            timeline=lead_data.get(
                "timeline",
                ""
            ),

            use_case=lead_data.get(
                "use_case",
                ""
            ),

            lead_quality=lead_data.get(
                "lead_quality",
                ""
            )

        )

        db.add(new_lead)

        db.commit()

        db.close()

        # FINAL AI RESPONSE
        ai_reply = f"""
Lead qualification completed successfully.

Summary:
- Company Size: {lead_data.get('company_size')}
- Budget: {lead_data.get('budget')}
- Timeline: {lead_data.get('timeline')}
- Use Case: {lead_data.get('use_case')}
- Lead Quality: {lead_data.get('lead_quality')}
"""

        # RESET MEMORY
        conversation_memory.clear()

    return {
        "reply": ai_reply,
        "lead_data": lead_data
    }


# GET ALL LEADS
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