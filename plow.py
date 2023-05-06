from fastecdsa import keys, curve
from ellipticcurve.privateKey import PrivateKey
from numba import jit, cuda
import platform
import multiprocessing
import hashlib
import binascii
import os
import sys
import time
import cupy as cp

DATABASE = r'database/11_13_2022/'

@jit(target_backend='numba.cuda')
def generate_private_key():
    return binascii.hexlify(cp.random.bytes(32)).decode('utf-8').upper()

def private_key_to_public_key(private_key, fastecdsa):
    if fastecdsa:
        key = keys.get_public_key(int('0x' + private_key, 0), curve.secp256k1)
        return '04' + (hex(key.x)[2:] + hex(key.y)[2:]).zfill(128)
    else:
        pk = PrivateKey().fromString(bytes.fromhex(private_key))
        return '04' + pk.publicKey().toString().hex().upper()

def public_key_to_address(public_key):
    output = []
    alphabet = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'
    var = hashlib.new('ripemd160')
    encoding = binascii.unhexlify(public_key.encode())
    var.update(hashlib.sha256(encoding).digest())
    var_encoded = ('00' + var.hexdigest()).encode()
    digest = hashlib.sha256(binascii.unhexlify(var_encoded)).digest()
    var_hex = '00' + var.hexdigest() + hashlib.sha256(digest).hexdigest()[0:8]
    count = [char != '0' for char in var_hex].index(True) // 2
    n = int(var_hex, 16)
    while n > 0:
        n, remainder = divmod(n, 58)
        output.append(alphabet[remainder])
    for i in range(count): output.append(alphabet[0])
    return ''.join(output[::-1])

def private_key_to_wif(private_key):
    digest = hashlib.sha256(binascii.unhexlify('80' + private_key)).hexdigest()
    var = hashlib.sha256(binascii.unhexlify(digest)).hexdigest()
    var = binascii.unhexlify('80' + private_key + var[0:8])
    alphabet = chars = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'
    value = pad = 0
    result = ''
    for i, c in enumerate(var[::-1]): value += 256**i * c
    while value >= len(alphabet):
        div, mod = divmod(value, len(alphabet))
        result, value = chars[mod] + result, div
    result = chars[value] + result
    for c in var:
        if c == 0: pad += 1
        else: break
    return chars[0] * pad + result

def main(database, args):
    while True:
        private_key = generate_private_key()
        public_key = private_key_to_public_key(private_key, args['fastecdsa']) 
        address = public_key_to_address(public_key)

        if args['verbose']:
            print(address)
        
        if address[-args['substring']:] in database:
            for filename in os.listdir(DATABASE):
                with open(DATABASE + filename) as file:
                    if address in file.read():
                        with open('plutus.txt', 'a') as plutus:
                            plutus.write('hex private key: ' + str(private_key) + '\n' +
                                         'WIF private key: ' + str(private_key_to_wif(private_key)) + '\n'
                                         'public key: ' + str(public_key) + '\n' +
                                         'uncompressed address: ' + str(address) + '\n\n')
                        break

def print_help():
    print('''ballllin........................................................................


Speed test: 
cpu_count: number of cores to run concurrently. More cores = more resource usage but faster bruteforcing. Omit this parameter to run with the maximum number of cores''')
    sys.exit(0)

def timer(args):
    start = time.time()
    private_key = generate_private_key()
    public_key = private_key_to_public_key(private_key, args['fastecdsa'])
    address = public_key_to_address(public_key)
    end = time.time()
    print(str(end - start))
    sys.exit(0)

if __name__ == '__main__':
    args = {
        'verbose': 0,
        'substring': 8,
        'fastecdsa': platform.system() in ['Linux', 'Darwin'],
        'cpu_count': multiprocessing.cpu_count(),
    }
    
    for arg in sys.argv[1:]:
        command = arg.split('=')[0]
        if command == 'help':
            print_help()
        elif command == 'time':
            timer(args)
        elif command == 'cpu_count':
            cpu_count = int(arg.split('=')[1])
            if cpu_count > 0 and cpu_count <= multiprocessing.cpu_count():
                args['cpu_count'] = cpu_count
            else:
                print('invalid input. cpu_count must be greater than 0 and less than or equal to ' + str(multiprocessing.cpu_count()))
                sys.exit(-1)
        elif command == 'verbose':
            verbose = arg.split('=')[1]
            if verbose in ['0', '1']:
                args['verbose'] = verbose
            else:
                print('invalid input. verbose must be 0(false) or 1(true)')
                sys.exit(-1)
        elif command == 'substring':
            substring = int(arg.split('=')[1])
            if substring > 0 and substring < 27:
                args['substring'] = substring
            else:
                print('invalid input. substring must be greater than 0 and less than 27')
                sys.exit(-1)
        else:
            print('invalid input: ' + command  + '\nrun `python3 plutus.py help` for help')
            sys.exit(-1)
    
    print('reading database files...')
    database = set()
    for filename in os.listdir(DATABASE):
        with open(DATABASE + filename) as file:
            for address in file:
                address = address.strip()
                if address.startswith('1'):
                    database.add(address[-args['substring']:])
    print('DONE')

    print('database size: ' + str(len(database)))
    print('processes spawned: ' + str(args['cpu_count']))
    
    for cpu in range(args['cpu_count']):
        multiprocessing.Process(target = main, args = (database, args)).start()
