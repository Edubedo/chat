from socket import *
import sys
import os
import threading
import tkinter as tk  # Tkinter es la librería gráfica de Python que permite crear interfaces de usuario de escritorio
from tkinter import filedialog, scrolledtext, messagebox
from datetime import datetime # Importamos la librería datetime para obtener la fecha y hora actual

IPServidor = "localhost"
puertoServidor = 9096

# Se declara e inicializa el socket del cliente
try:
    # AF_INET: Protocolo de direcciones IP
    # SOCK_STREAM: Protocolo de comunicación TCP
    socketCliente = socket(AF_INET, SOCK_STREAM)
    socketCliente.connect((IPServidor, puertoServidor))
    print(f"Conectado al servidor {IPServidor}:{puertoServidor}")
except ConnectionRefusedError:
    print("Error: No se pudo conectar al servidor. Asegúrate de que está encendido.")
    sys.exit()

# Manejo de los usuarios, tanto el que esta escribiendo como los demas conectados
usuario_interno = None
usuario_externo = None

socket_abierto = True

def recibir_mensajes():
    """Función que se ejecuta en un hilo separado para recibir mensajes del servidor."""
    global socket_abierto, usuario_interno
    while socket_abierto:
        try:
            respuesta = socketCliente.recv(4096).decode()

            if not respuesta:
                print("El servidor cerró la conexión.")
                socketCliente.close()
                socket_abierto = False
                break

            if respuesta.startswith("Error:") or "exitoso" in respuesta: # Manejamos los errores
                if "Bienvenido" in respuesta:
                    usuario_interno = respuesta.split()[-1]
                messagebox.showinfo("Información", respuesta)
            else:
                chat_text.config(state=tk.NORMAL)
                fecha_creacion = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                if respuesta.startswith(f"{usuario_interno}:"):
                    chat_text.insert(tk.END, f"({fecha_creacion} - {usuario_interno}): {respuesta[len(usuario_interno)+2:]}\n")
                else:
                    chat_text.insert(tk.END, f"({fecha_creacion} - {respuesta}\n") # Estamos importando el usuario para resolver un error de sesión
                chat_text.config(state=tk.DISABLED)

        except Exception as e:
            print(f"Error al recibir mensaje: {e}")
            socketCliente.close()
            socket_abierto = False
            break

def abrir_ventana_registro():
    """Abre una nueva ventana para el registro de usuarios."""
    ventana_registro = tk.Toplevel(root)
    ventana_registro.title("Registro de Usuario")
    ventana_registro.geometry("350x150")

    # Centrar la ventana en la pantalla windows
    ventana_registro.update_idletasks()
    ancho_ventana = ventana_registro.winfo_width()
    alto_ventana = ventana_registro.winfo_height()
    x = (ventana_registro.winfo_screenwidth() // 2) - (ancho_ventana // 2)
    y = (ventana_registro.winfo_screenheight() // 2) - (alto_ventana // 2)
    ventana_registro.geometry(f"{ancho_ventana}x{alto_ventana}+{x}+{y}")

    tk.Label(ventana_registro, text="Correo:").grid(row=0, column=0, padx=5, pady=5)
    correo_entry = tk.Entry(ventana_registro, width=40)
    correo_entry.grid(row=0, column=1, padx=5, pady=5)

    tk.Label(ventana_registro, text="Usuario:").grid(row=1, column=0, padx=5, pady=5)
    usuario_entry = tk.Entry(ventana_registro, width=40)
    usuario_entry.grid(row=1, column=1, padx=5, pady=5)

    tk.Label(ventana_registro, text="Contraseña:").grid(row=2, column=0, padx=5, pady=5)
    password_entry = tk.Entry(ventana_registro, width=40, show="*")
    password_entry.grid(row=2, column=1, padx=5, pady=5)

    def registrar_usuario():
        global usuario_interno
        #  Obtenemos los valores que ingreso el usuario en los campos
        correo = correo_entry.get()
        usuario_interno = usuario_entry.get()
        password = password_entry.get()
        if correo and usuario_interno and password:
            registro_info = f"REGISTRO {correo} {usuario_interno} {password}"

            # Enviamos un mensaje al servidor con la información del registro
            socketCliente.send(registro_info.encode())

            # La venta de registro se cierra
            ventana_registro.destroy()
        else:
            # Sí no ingresa todo lso campos le decimos que tienen que ingresar todos los campos
            messagebox.showwarning("Registro", "Todos los campos son obligatorios.")

    # Cuando le da click a registrar se ejecuta la función registrar_usuario
    boton_registrar = tk.Button(ventana_registro, text="Registrar", command=registrar_usuario)
    boton_registrar.grid(row=3, columnspan=2, pady=10)

def abrir_ventana_login():
    """Abre una nueva ventana para el inicio de sesión."""
    ventana_login = tk.Toplevel(root)
    ventana_login.title("Inicio de Sesión")
    ventana_login.geometry("350x150")

    tk.Label(ventana_login, text="Correo:").grid(row=0, column=0, padx=5, pady=5)
    correo_entry = tk.Entry(ventana_login, width=40)
    correo_entry.grid(row=0, column=1, padx=5, pady=5)
    correo_entry.focus()


    tk.Label(ventana_login, text="Contraseña:").grid(row=1, column=0, padx=5, pady=5)
    password_entry = tk.Entry(ventana_login, width=40, show="*")
    password_entry.grid(row=1, column=1, padx=5, pady=5)

    def iniciar_sesion():
        global usuario_interno
        correo = correo_entry.get() 
        password = password_entry.get()
        if correo and password:
            login_info = f"LOGIN {correo} {password}"
            socketCliente.send(login_info.encode())
            ventana_login.destroy()
        else:
            messagebox.showwarning("Inicio de Sesión", "Todos los campos son obligatorios.")

    boton_login = tk.Button(ventana_login, text="Iniciar Sesión", command=iniciar_sesion)
    boton_login.grid(row=2, columnspan=2, pady=10)

def enviar_mensaje():
    global socket_abierto
    mensaje = mensaje_entry.get()
    if mensaje and socket_abierto:
        try:
            socketCliente.send(mensaje.encode())
            chat_text.config(state=tk.NORMAL)
            fecha_creacion = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            chat_text.insert(tk.END, f"({usuario_interno if usuario_interno else socketCliente.getsockname()} - {fecha_creacion}): {mensaje}\n")
            chat_text.config(state=tk.DISABLED)
            mensaje_entry.delete(0, tk.END)
            if mensaje.lower() in ['adios', 'bye']:
                socketCliente.close()
                socket_abierto = False
                root.quit()
        except OSError as e:
            print(f"Error al enviar mensaje: {e}")
            messagebox.showerror("Error", "No se pudo enviar el mensaje. La conexión con el servidor se ha perdido.")

# Configuración de la interfaz gráfica
root = tk.Tk()
root.title("Chatubedo 1.1")
# Show the active users

root.geometry("800x600")
# Agregar icono
icon_path = os.path.join(os.path.dirname(__file__), "assets", "logo.ico")
root.iconbitmap(icon_path)


chat_text = scrolledtext.ScrolledText(root, state=tk.DISABLED, wrap=tk.WORD)
chat_text.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

mensaje_entry = tk.Entry(root)
mensaje_entry.pack(padx=10, pady=5, fill=tk.X, expand=True)

boton_enviar = tk.Button(root, text="Enviar", command=enviar_mensaje)
boton_enviar.pack(padx=10, pady=5, side=tk.LEFT)

boton_registrar = tk.Button(root, text="Registrar", command=abrir_ventana_registro)
boton_registrar.pack(padx=10, pady=5, side=tk.RIGHT)

boton_login = tk.Button(root, text="Iniciar Sesión", command=abrir_ventana_login)
boton_login.pack(padx=10, pady=5, side=tk.RIGHT)

# Iniciar el hilo que se encargará de recibir mensajes del servidor
hilo_recibir = threading.Thread(target=recibir_mensajes, daemon=True)
hilo_recibir.start()

root.mainloop()