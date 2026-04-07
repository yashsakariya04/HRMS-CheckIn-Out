# schemas/employee.py

from pydantic import BaseModel, EmailStr
import uuid

class CreateEmployeeRequest(BaseModel):
    email: EmailStr
    department_id: uuid.UUID
    designation: str
    
    
class UpdateProfileRequest(BaseModel):
    full_name: str
    photo_url: str | None = None    