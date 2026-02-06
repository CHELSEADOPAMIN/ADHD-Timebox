import datetime
import sys
import os

# Add backend directory to sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), "."))

from tools.ics_tools import build_ics

def test_ics_generation():
    print("Testing ICS generation...")
    
    today = datetime.date.today()
    tasks = [
        {
            "id": "1",
            "title": "Test Task 1",
            "start": f"{today} 10:00",
            "end": f"{today} 11:00",
            "status": "pending",
            "type": "work"
        },
        {
            "id": "2",
            "title": "Test Task 2",
            "start": f"{today} 14:00",
            "end": f"{today} 15:00",
            "status": "completed",
            "type": "break"
        }
    ]
    
    ics_content = build_ics(tasks, today)
    
    print("\n--- ICS Content Start ---")
    print(ics_content)
    print("--- ICS Content End ---\n")
    
    assert "BEGIN:VCALENDAR" in ics_content
    assert "END:VCALENDAR" in ics_content
    assert "SUMMARY:Test Task 1" in ics_content
    assert "SUMMARY:Test Task 2" in ics_content
    assert "STATUS:CONFIRMED" in ics_content
    assert "STATUS:COMPLETED" in ics_content
    
    print("✅ ICS generation test passed!")

if __name__ == "__main__":
    test_ics_generation()
