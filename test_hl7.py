import random
import requests
import argparse
from datetime import datetime
import os

# File to store the last used accession number
COUNTER_FILE = 'accession_counter.txt'

def get_next_accession_number():
    """Get the next accession number in sequence."""
    try:
        # Try to read the last used number
        if os.path.exists(COUNTER_FILE):
            with open(COUNTER_FILE, 'r') as f:
                last_number = int(f.read().strip())
        else:
            last_number = 0
        
        # Increment the number
        next_number = last_number + 1
        
        # Save the new number immediately
        with open(COUNTER_FILE, 'w') as f:
            f.write(str(next_number))
        
        # Format with leading zeros
        return f"VAR{next_number:07d}"
    except Exception as e:
        print(f"Error managing accession numbers: {e}")
        # Fallback to random number if there's an error
        return f"VAR{random.randint(1000000, 9999999)}"

def generate_hl7_message(accession_number):
    """Generate a Gleamer-like HL7 message."""
    # Randomly choose POSITIVE or NEGATIVE
    result = random.choice(['POSITIVE', 'NEGATIVE'])
    
    # Current timestamp
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    
    # Generate HL7 message
    message = f"""MSH|^~\\&|GLEAMER|HOSPITAL|RAD|HOSPITAL|{timestamp}||ORU^R01|{accession_number}|P|2.5
PID|1||{accession_number}|||19700101|M
PV1|1|O|RAD
ORC|RE|{accession_number}|||CM
OBR|1|{accession_number}||CT CHEST||{timestamp}|||||||||||||||CM
OBX|1|ST|AI_RESULT||{result}||||||F
"""
    return message

def send_hl7_message(message):
    """Send HL7 message to the application."""
    url = 'http://127.0.0.1:5000/api/hl7'
    headers = {
        'Content-Type': 'text/plain',
        'Content-Length': str(len(message))
    }
    
    try:
        response = requests.post(url, data=message, headers=headers)
        print(f"Status Code: {response.status_code}")
        if response.status_code != 200:
            print(f"Error: {response.text}")
        return response.status_code == 200
    except Exception as e:
        print(f"Error sending message: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description='Generate and send HL7 test messages')
    parser.add_argument('-n', '--number', type=int, default=1,
                      help='Number of messages to generate (default: 1)')
    args = parser.parse_args()
    
    successful = 0
    failed = 0
    
    print(f"\nGenerating {args.number} test cases...")
    
    for i in range(args.number):
        accession_number = get_next_accession_number()
        message = generate_hl7_message(accession_number)
        
        print(f"\nTest case {i+1}/{args.number}")
        print(f"Accession Number: {accession_number}")
        print("HL7 Message:")
        print("-" * 50)
        print(message)
        print("-" * 50)
        
        if send_hl7_message(message):
            successful += 1
        else:
            failed += 1
    
    print(f"\nSummary:")
    print(f"Total cases: {args.number}")
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")

if __name__ == '__main__':
    main() 