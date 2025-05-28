import random
import socket
import argparse
from datetime import datetime
import os
import time

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

def generate_finnish_id():
    """Generate a Finnish citizen ID number (ddmmyy-xxxx)."""
    # Generate random date between 1950 and 2000
    year = random.randint(50, 99)  # Last two digits of year
    month = random.randint(1, 12)
    day = random.randint(1, 28)
    
    # Generate random 4-digit number
    number = random.randint(1, 9999)
    
    # Format as ddmmyy-xxxx
    return f"{day:02d}{month:02d}{year:02d}-{number:04d}"

def generate_hl7_message(accession_number):
    """Generate a BoneView-like HL7 message with Finnish ID."""
    # Generate result with 10% chance of DOUBT, 45% each for POSITIVE and NEGATIVE
    rand = random.random()
    if rand < 0.1:  # 10% chance for DOUBT
        result = 'DOUBT'
    elif rand < 0.55:  # 45% chance for POSITIVE
        result = 'POSITIVE'
    else:  # 45% chance for NEGATIVE
        result = 'NEGATIVE'
    
    # Current timestamp with milliseconds
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S.%f')[:-3]
    
    # Generate Finnish ID and study UID
    patient_id = generate_finnish_id()
    study_uid = f"1.2.392.200036.9125.2.691202139174.{accession_number}"
    
    # Extract DOB from Finnish ID (ddmmyy)
    dob = f"19{patient_id[4:6]}{patient_id[2:4]}{patient_id[0:2]}"  # Convert to YYYYMMDD
    
    # Determine gender from the last digit of the ID
    gender = 'F' if int(patient_id[-1]) % 2 == 0 else 'M'
    
    # Generate HL7 message
    message = f"""MSH|^~\\&|GLEAMER||CSILXD|LUXMED|{timestamp}||ORU^R01|{accession_number}|P|2.5||||||UNICODE UTF-8|||
PID||{patient_id}|||TEST^PATIENT||{dob}|{gender}||||||
OBR|1|{accession_number}||Boneview analysis||||
OBX|1|ST|result-code^^GLEAMER||{result}||||||R||||||||{accession_number}
ZDS|{study_uid}^Gleamer^Application^DICOM
"""
    return message

def send_mllp_message(message, host='localhost', port=8000):
    """Send HL7 message to the MLLP server."""
    try:
        # Create socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((host, port))
        
        # MLLP framing: VT (0x0B) at start, FS (0x1C) at end, CR (0x0D) after FS
        mllp_message = chr(0x0B) + message + chr(0x1C) + chr(0x0D)
        
        # Send message
        sock.send(mllp_message.encode())
        
        # Receive acknowledgment with timeout
        sock.settimeout(5.0)  # 5 second timeout
        ack = sock.recv(4096)
        
        # Close socket
        sock.close()
        
        # Check if we got a valid ACK
        if ack:
            try:
                ack_str = ack.decode()
                print("Received acknowledgment:", ack_str)
                # Check if it's a valid ACK (contains MSA segment)
                if "MSA|AA|" in ack_str:
                    return True
                elif "MSA|AE|" in ack_str or "MSA|AR|" in ack_str:
                    print("Received error acknowledgment")
                    return False
            except UnicodeDecodeError:
                print("Received invalid acknowledgment (not UTF-8)")
                return False
        return False
        
    except socket.timeout:
        print("Timeout waiting for acknowledgment")
        return False
    except Exception as e:
        print(f"Error sending MLLP message: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description='Generate and send HL7 test messages via MLLP')
    parser.add_argument('-n', '--number', type=int, default=1,
                      help='Number of messages to generate (default: 1)')
    parser.add_argument('-p', '--port', type=int, default=8000,
                      help='MLLP server port (default: 8000)')
    parser.add_argument('-H', '--host', type=str, default='localhost',
                      help='MLLP server host (default: localhost)')
    parser.add_argument('-d', '--delay', type=float, default=1.0,
                      help='Delay between messages in seconds (default: 1.0)')
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
        
        if send_mllp_message(message, args.host, args.port):
            successful += 1
        else:
            failed += 1
        
        # Add delay between messages
        if i < args.number - 1:  # Don't delay after the last message
            time.sleep(args.delay)
    
    print(f"\nSummary:")
    print(f"Total cases: {args.number}")
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")

if __name__ == '__main__':
    main() 