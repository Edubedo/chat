from socket import *
import threading
import queue
import os
import psycopg2
import uuid
from dotenv import load_dotenv

# Cargar variables de entorno desde el archivo .env
load_dotenv()

direccionServidor = os.getenv("SERVER_HOST", "0.0.0.0")
try:
    puertoServidor = int(os.getenv("PORT", 9096))
except ValueError:
    puertoServidor = 9000
    
# Crear el socket del servidor y ponerlo a escuchar
socketServidor = socket(AF_INET, SOCK_STREAM)
socketServidor.bind((direccionServidor, puertoServidor))
socketServidor.listen()

# Contador de usuarios activos
usuarios_activos = 0

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

def registrar_usuario(socketConexion, correo, usuario, password):
    """Registra un nuevo usuario en la base de datos."""
    try:
        connection = psycopg2.connect(
            host=os.getenv("DB_HOST"),
            database=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            port=os.getenv("DB_PORT")
        )
        cursor = connection.cursor()

        # Verificar que el correo ya exista en la base de datos
        cursor.execute("SELECT * FROM users WHERE s_correo = %s", (correo,))
        resultado = cursor.fetchone()
        if resultado:
            socketConexion.send("Error: El correo ya está registrado.".encode())
            cursor.close()
            connection.close()
            return

        # Insertar el nuevo usuario en la base de datos
        query = """
        INSERT INTO users (sk_user, s_correo, sk_password, s_usuario)
        VALUES (%s, %s, %s, %s)
        """
        sk_user = uuid.uuid4()
        cursor.execute(query, (str(sk_user), correo, password, usuario))
        connection.commit()
        cursor.close()
        connection.close()
        socketConexion.send("Registro exitoso".encode())
        print(f"Usuario {usuario} registrado exitosamente.")
    except Exception as error:
        print(f"Error al registrar el usuario: {error}")
        socketConexion.send(f"Error al registrar el usuario: {error}".encode())

def iniciar_sesion(socketConexion, correo, password):
    """Valida el correo y la contraseña del usuario y devuelve el nombre de usuario."""
    try:
        connection = psycopg2.connect(
            host=os.getenv("DB_HOST"),
            database=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            port=os.getenv("DB_PORT")
        )
        cursor = connection.cursor()

        # Verificar el correo y la contraseña en la base de datos
        cursor.execute("SELECT s_usuario FROM users WHERE s_correo = %s AND sk_password = %s", (correo, password))
        resultado = cursor.fetchone()
        if resultado:
            usuario = resultado[0]
            socketConexion.send(f"Inicio de sesión exitoso. Bienvenido {usuario}".encode())
            print(f"Usuario {usuario} inició sesión exitosamente.")
            return usuario
        else:
            socketConexion.send("Error: Correo o contraseña incorrectos.".encode())
            return None
        
        cursor.close()
        connection.close()
    except Exception as error:
        print(f"Error al iniciar sesión: {error}")
        socketConexion.send(f"Error al iniciar sesión: {error}".encode())
        return None

def manejar_cliente(socketConexion, addr):
    print(f"Cliente conectado desde {addr}")
    global usuarios_activos
    usuarios_activos += 1

    print("CURRENT USERS: ", usuarios_activos)
    
    # Enviar todos los mensajes almacenados en la base de datos al cliente
    mensajes = obtener_mensajes_de_db()
    for mensaje in mensajes:
        try:
            contenido, sk_user, fecha_creacion = mensaje
            socketConexion.send(f"({sk_user} - {fecha_creacion}): {contenido}\n".encode())
        except OSError:
            print(f"Error al enviar historial a {addr}")
            socketConexion.close()
            return
    
    usuario = None  # Inicializar la variable usuario

    while True:
        try:    
            mensajeRecibido = socketConexion.recv(4096).decode()
            if not mensajeRecibido:
                break  # El cliente cerró la conexión
            print(f"Mensaje recibido de {addr}: {mensajeRecibido}")

            if mensajeRecibido.startswith("REGISTRO"):
                _, correo, usuario, password = mensajeRecibido.split(maxsplit=3)
                registrar_usuario(socketConexion, correo, usuario, password)
                continue

            if mensajeRecibido.startswith("LOGIN"):
                _, correo, password = mensajeRecibido.split(maxsplit=2)
                usuario = iniciar_sesion(socketConexion, correo, password)
                continue

            # Guardar el mensaje en la base de datos
            guardar_mensaje_en_db(addr, mensajeRecibido, usuario if usuario else addr[0])

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
                        cliente.send(f"{usuario if usuario else addr[0]}: {mensajeRecibido}".encode()) # Enviar el mensaje recibido al cliente
                    except OSError:
                        print(f"Error al reenviar mensaje a {cliente.getpeername()}")
                        cliente.close()
                        clientes.remove((cliente, _))

            # Agregar el mensaje a la cola para que el operador lo responda
            cola_mensajes.put((socketConexion, addr, mensajeRecibido))
        except ConnectionResetError:
            print(f"Cliente {addr} se desconectó del servidor.")
            usuarios_activos -= 1
            print("CURRENT USERS: ", usuarios_activos)
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

def guardar_mensaje_en_db(addr, mensaje, usuario):
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
        INSERT INTO messages (sk_message, s_content, d_fecha_creacion, sk_user, s_address)
        VALUES (%s, %s, NOW(), %s, %s)
        """
        # Generar un UUID para sk_message
        sk_message = uuid.uuid4()
        cursor.execute(query, (str(sk_message), mensaje, usuario, str(addr[0])))
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

# Mientras el servidor se encuentre activo
while servidor_activo:
    try:
        # Aceptamos las peticios del cliente
        socketConexion, addr = socketServidor.accept()

        # Guardamos en una peticion la conexion y la direccion del cliente
        clientes.append((socketConexion, addr))

        
        hilo_cliente = threading.Thread(target=manejar_cliente, args=(socketConexion, addr))
        hilo_cliente.start()
    except OSError:
        break  # Si el servidor se cierra, se rompe el bucle