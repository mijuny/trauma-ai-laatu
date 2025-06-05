import logging
import socket
import threading
import os
from datetime import datetime
from hl7 import parse
from pekka2000 import app, db, Study, parse_hl7_message

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def find_available_port(start_port=8000, max_attempts=100):
    """Find an available port starting from start_port."""
    for port in range(start_port, start_port + max_attempts):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('', port))
                return port
        except OSError:
            continue
    raise OSError("No available ports found")

class HL7MLLPServer:
    def __init__(self, host='0.0.0.0', port=None):
        self.host = host
        # Get port from environment variable or find an available port
        try:
            self.port = int(os.getenv('MLLP_PORT', port or 8000))
        except ValueError:
            logger.warning("Invalid port number in MLLP_PORT, using default range")
            self.port = 8000
        
        # If port is not specified, find an available one
        if not port and not os.getenv('MLLP_PORT'):
            try:
                self.port = find_available_port(self.port)
                logger.info(f"Using port {self.port} for MLLP server")
            except OSError as e:
                logger.error(f"Could not find available port: {e}")
                raise
        
        self.running = False
        self.server_socket = None
    
    def start(self):
        """Start the MLLP server."""
        self.running = True
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        try:
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(5)
            logger.info(f"Starting HL7 MLLP server on {self.host}:{self.port}")
            logger.info(f"To use this port, set MLLP_PORT={self.port} in your environment")
            
            while self.running:
                try:
                    client_socket, address = self.server_socket.accept()
                    logger.info(f"Accepted connection from {address}")
                    client_thread = threading.Thread(
                        target=self.handle_client,
                        args=(client_socket, address)
                    )
                    client_thread.start()
                except Exception as e:
                    if self.running:
                        logger.error(f"Error accepting connection: {e}")
        
        except OSError as e:
            if e.errno == 48:  # Address already in use
                logger.error(f"Port {self.port} is already in use. Please try a different port by setting MLLP_PORT environment variable.")
            else:
                logger.error(f"Error starting MLLP server: {e}")
            self.running = False
            raise
        finally:
            if self.server_socket:
                self.server_socket.close()
    
    def stop(self):
        """Stop the MLLP server."""
        self.running = False
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
    
    def handle_client(self, client_socket, address):
        """Handle a client connection."""
        try:
            # MLLP message starts with 0x0B (VT) and ends with 0x1C (FS)
            message = ""
            start_char = False
            
            while True:
                data = client_socket.recv(4096)
                if not data:
                    break
                
                for byte in data:
                    if byte == 0x0B:  # Start of message
                        start_char = True
                        message = ""
                    elif byte == 0x1C:  # End of message
                        if start_char:
                            self.process_message(message, client_socket)
                        start_char = False
                    elif start_char:
                        message += chr(byte)
        
        except Exception as e:
            logger.error(f"Error handling client {address}: {e}")
        finally:
            try:
                client_socket.close()
            except:
                pass
    
    def process_message(self, message, client_socket):
        """Process an HL7 message and send acknowledgment."""
        try:
            logger.info(f"Received HL7 message: {message}")
            
            # Process message using existing parse_hl7_message function
            with app.app_context():
                result = parse_hl7_message(message)
                
                if result:
                    # Store in database
                    study = Study(
                        accession_number=result['accession_number'],
                        study_description=result['study_description'],
                        raw_hl7=message,
                        parsed_data=result,
                        ai_classification=result['ai_classification']
                    )
                    db.session.add(study)
                    db.session.commit()
                    
                    # Send ACK
                    ack = self.create_ack(message, 'AA')
                else:
                    logger.error("Failed to parse HL7 message")
                    ack = self.create_ack(message, 'AE')
            
            # Send acknowledgment with MLLP framing
            if ack:
                ack_message = chr(0x0B) + ack + chr(0x1C) + chr(0x0D)
                client_socket.send(ack_message.encode())
            
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            try:
                ack = self.create_ack(message, 'AR')
                if ack:
                    ack_message = chr(0x0B) + ack + chr(0x1C) + chr(0x0D)
                    client_socket.send(ack_message.encode())
            except:
                pass
    
    def create_ack(self, original_message, ack_code):
        """Create HL7 acknowledgment message."""
        try:
            # Parse the original message to get message control ID
            h = parse(original_message)
            msg_control_id = str(h.segment('MSH')[9][0]) if h.segment('MSH') else 'UNKNOWN'
            
            # Create acknowledgment message
            ack_message = f"""MSH|^~\\&|HOSPITAL|RAD|GLEAMER|HOSPITAL|{datetime.now().strftime('%Y%m%d%H%M%S')}||ACK^R01|{msg_control_id}|P|2.5
MSA|{ack_code}|{msg_control_id}"""
            
            return ack_message
        except Exception as e:
            logger.error(f"Error creating ACK message: {e}")
            return None

if __name__ == '__main__':
    server = HL7MLLPServer()
    try:
        server.start()
    except KeyboardInterrupt:
        server.stop() 