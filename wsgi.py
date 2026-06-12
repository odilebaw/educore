import sys
import os

# PythonAnywhere uchun yo'l
# Real deployment da '/home/yourusername/educore' bo'ladi
project_path = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_path)

from app import app as application
