from socket import *
import threading
import queue
import os
import psycopg2
import uuid
from dotenv import load_dotenv

# Cargar variables de entorno desde el archivo .env
load_dotenv()

direccionServidor = os.getenv("SERVER_HOST")
puertoServidor = int(os.getenv("SERVER_PORT"))

# Crear el socket del servidor y ponerlo a escuchar
socketServidor = socket(AF_INET, SOCK_STREAM)
socketServidor.bind((direccionServidor, puertoServidor))
socketServidor.listen()

clientes = []                      # Lista para guardar los clientes conectados
cola_mensajes = queue.Queue()      # Cola FIFO para los mensajes recibidos de clientes
servidor_activo = True             # Bandera para saber si el servidor sigue activo

def obtener_mensajes_de_db():
    """Obtiene todos los mensajes almacenados en la base de datos."""
    try:
        connection = psycopg2.connect(
            host=os.getenv("DB_HOST"),
            database=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            port=os.getenv("DB_PORT")
        )
        cursor = connection.cursor()
        query = "SELECT s_content, sk_user, d_fecha_creacion FROM messages ORDER BY d_fecha_creacion"
        cursor.execute(query)
        mensajes = cursor.fetchall()
        cursor.close()
        connection.close()
        return mensajes
    except Exception as error:
        print(f"Error al obtener mensajes de la base de datos: {error}")
        return []

def manejar_cliente(socketConexion, addr):
    print(f"Cliente conectado desde {addr}")
    
    # Enviar todos los mensajes almacenados en la base de datos al cliente
    mensajes = obtener_mensajes_de_db()
    for mensaje in mensajes:
        print("mensaje: ", mensaje)
        try:
            contenido, sk_user, fecha_creacion = mensaje
            socketConexion.send(f"({sk_user} - {fecha_creacion}): {contenido} \n".encode())
        except OSError:
            print(f"Error al enviar historial a {addr}")
            socketConexion.close()
            return
    
    while True:
        try:    
            mensajeRecibido = socketConexion.recv(4096).decode()
            if not mensajeRecibido:
                break  # El cliente cerró la conexión
            print(f"Mensaje recibido de {addr}: {mensajeRecibido}")

            # Guardar el mensaje en la base de datos
            guardar_mensaje_en_db(addr, mensajeRecibido)

            # Si el cliente quiere enviar un archivo
            if mensajeRecibido.startswith("ENVIAR_ARCHIVO"):
                _, nombre_archivo = mensajeRecibido.split(maxsplit=1)
                confirmar_envio(socketConexion, nombre_archivo)
                continue  # Espera nuevos mensajes

            # Si el cliente dice "adios" o "bye", se desconecta
            if mensajeRecibido.lower() in ['adios', 'bye']:
                print(f"Cliente {addr} desconectado.")
                socketConexion.close()
                try:
                    clientes.remove((socketConexion, addr))
                except ValueError:
                    pass
                break

            # Reenviar el mensaje a todos los clientes conectados
            for cliente, _ in clientes:
                if cliente != socketConexion:
                    try:
                        cliente.send(f"{mensajeRecibido}".encode()) # Enviar el mensaje recibido al cliente
                    except OSError:
                        print(f"Error al reenviar mensaje a {cliente.getpeername()}")
                        cliente.close()
                        clientes.remove((cliente, _))

            # Agregar el mensaje a la cola para que el operador lo responda
            cola_mensajes.put((socketConexion, addr, mensajeRecibido))
        except ConnectionResetError:
            print(f"Cliente {addr} se desconectó abruptamente.")
            socketConexion.close()
            try:
                clientes.remove((socketConexion, addr))
            except ValueError:
                pass
            break

def operator_input():
    """
    Esta función corre en un hilo independiente y permite al operador
    escribir comandos en cualquier momento, incluso si no hay mensajes pendientes.
    Si se escribe 'adios' o 'bye', se cierra el servidor.
    Si hay un mensaje pendiente, se usa el texto escrito como respuesta.
    """
    global servidor_activo
    while servidor_activo:
        try:
            comando = input("Servidor: ")
            if comando.lower() in ['adios', 'bye']:
                print("Cerrando servidor...")
                servidor_activo = False
                cerrar_servidor()
                break
            # Si hay mensajes pendientes, enviar la respuesta al primer mensaje de la cola
            if not cola_mensajes.empty():
                socketConexion, addr, mensajeRecibido = cola_mensajes.get()
                try:
                    socketConexion.send(comando.encode())
                except OSError:
                    print(f"Error al enviar respuesta a {addr}")
                    socketConexion.close()
                    try:
                        clientes.remove((socketConexion, addr))
                    except ValueError:
                        pass
            else:
                print("No hay mensajes pendientes para responder.")
        except EOFError:
            print("Entrada estándar cerrada. Cerrando servidor...")
            servidor_activo = False
            cerrar_servidor()
            break
        
def cerrar_servidor():
    """Cierra todas las conexiones y finaliza el programa del servidor."""
    print("Desconectando todos los clientes...")
    for cliente, _ in clientes:
        try:
            cliente.close()
        except:
            pass
    socketServidor.close()
    os._exit(0)

def guardar_mensaje_en_db(addr, mensaje):
    """Guarda el mensaje recibido en la base de datos."""
    try:
        connection = psycopg2.connect(
            host=os.getenv("DB_HOST"),
            database=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            port=os.getenv("DB_PORT")
        )
        cursor = connection.cursor()
        query = """
        INSERT INTO messages (sk_message, s_content, d_fecha_creacion, sk_user)
        VALUES (%s, %s, NOW(), %s)
        """
        # Generar un UUID para sk_message
        sk_message = uuid.uuid4()
        # Convertir la dirección IP a un UUID
        cursor.execute(query, (str(sk_message), mensaje, str(addr[0])))
        connection.commit()
        cursor.close()
        connection.close()
    except Exception as error:
        print(f"Error al guardar el mensaje en la base de datos: {error}")

def confirmar_envio(socketConexion, nombre_archivo):
    """Pregunta al operador si se acepta recibir el archivo solicitado por el cliente."""
    print(f"\nEl cliente quiere enviar el archivo: {nombre_archivo}")
    aceptar = input("¿Aceptar archivo? (si/no): ").strip().lower()
    if aceptar == "si":
        socketConexion.send("ACEPTADO".encode())
        recibir_archivo(socketConexion, nombre_archivo)
    else:
        socketConexion.send("RECHAZADO".encode())
        print(f"Archivo {nombre_archivo} rechazado.")

def recibir_archivo(socketConexion, nombre_archivo):
    """Recibe y guarda el archivo enviado por el cliente."""
    with open(nombre_archivo, "wb") as archivo:
        while True:
            datos = socketConexion.recv(4096)
            if datos == b"FIN_ARCHIVO":
                break
            archivo.write(datos)
    print(f"Archivo {nombre_archivo} recibido correctamente.")


def connectDatabase():
    try:
        connection = psycopg2.connect(
            host=os.getenv("DB_HOST"),
            database=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            port=os.getenv("DB_PORT")
        )
        print("Conexión establecida")
    except Exception as error:
        print(f"Error al conectar a la base de datos: {error}")

hilo_operator = threading.Thread(target=operator_input, daemon=True)
hilo_operator.start()

connectDatabase()

while servidor_activo:
    try:
        socketConexion, addr = socketServidor.accept()
        clientes.append((socketConexion, addr))
        hilo_cliente = threading.Thread(target=manejar_cliente, args=(socketConexion, addr))
        hilo_cliente.start()
    except OSError:
        break  # Si el servidor se cierra, se rompe el bucle