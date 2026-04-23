import socket
import urllib.parse
from _thread import start_new_thread
import mimetypes
import os

# Конфигурация сервера
HOST = 'localhost'  # Можно заменить на '' для доступа с других устройств
PORT = 8080         # 80 требует прав администратора, используем 8080

# Жестко заданные учетные данные
VALID_LOGIN = "admin"
VALID_PASSWORD = "12345"

def parse_request(request_data):
    """
    Парсит HTTP-запрос и возвращает метод, путь и параметры POST (если есть)
    """
    lines = request_data.split(b'\r\n')
    if not lines:
        return None, None, None
    
    # Парсим первую строку (Request Line)
    first_line = lines[0].decode('utf-8', errors='ignore')
    parts = first_line.split(' ')
    if len(parts) < 2:
        return None, None, None
    
    method = parts[0]
    path = parts[1]
    
    # Парсим POST-данные (если есть)
    post_params = {}
    if method == 'POST':
        # Ищем пустую строку, разделяющую заголовки и тело
        empty_line_index = request_data.find(b'\r\n\r\n')
        if empty_line_index != -1:
            body = request_data[empty_line_index + 4:]
            # Парсим параметры вида login=admin&password=12345
            body_str = body.decode('utf-8', errors='ignore')
            post_params = urllib.parse.parse_qs(body_str)
            # Преобразуем значения из списков в строки
            post_params = {k: v[0] for k, v in post_params.items()}
    
    return method, path, post_params

def handle_client(client_socket, client_address):
    """
    Обрабатывает подключение одного клиента
    """
    print(f"Новое подключение от {client_address}")
    
    try:
        # Получаем данные от клиента
        request_data = client_socket.recv(4096)
        if not request_data:
            client_socket.close()
            return
        
        # Парсим запрос
        method, path, post_params = parse_request(request_data)
        print(f"Запрос: {method} {path} от {client_address}")
        
        # МАРШРУТИЗАЦИЯ
        if method == 'GET':
            if path == '/' or path == '/login.html':
                # Отправляем HTML-форму
                send_static_file(client_socket, 'login.html', 'text/html')
            else:
                # Пытаемся отдать статический файл (для будущего расширения)
                send_static_file(client_socket, path.lstrip('/'))
        
        elif method == 'POST':
            if path == '/login':
                # Обрабатываем данные авторизации
                handle_login(client_socket, post_params)
            else:
                # 404 для неизвестного POST-пути
                send_error_response(client_socket, 404, "Not Found")
        else:
            # Метод не поддерживается
            send_error_response(client_socket, 405, "Method Not Allowed")
    
    except Exception as e:
        print(f"Ошибка при обработке клиента {client_address}: {e}")
        send_error_response(client_socket, 500, "Internal Server Error")
    
    finally:
        client_socket.close()
        print(f"Подключение от {client_address} закрыто")

def send_static_file(client_socket, filename, default_content_type=None):
    """
    Отправляет статический файл клиенту
    """
    # Защита от directory traversal (упрощенная)
    filename = os.path.basename(filename)
    
    # Определяем полный путь к файлу (в текущей директории)
    filepath = os.path.join(os.path.dirname(__file__), filename)
    
    try:
        with open(filepath, 'rb') as f:
            content = f.read()
        
        # Определяем MIME-тип
        if default_content_type:
            content_type = default_content_type
        else:
            content_type, _ = mimetypes.guess_type(filename)
            if not content_type:
                content_type = 'application/octet-stream'
        
        # Формируем успешный ответ
        response = (
            f"HTTP/1.1 200 OK\r\n"
            f"Content-Type: {content_type}; charset=utf-8\r\n"
            f"Content-Length: {len(content)}\r\n"
            f"Connection: close\r\n"
            f"\r\n"
        ).encode('utf-8') + content
        
        client_socket.send(response)
        print(f"Отправлен файл: {filename} ({content_type})")
        
    except FileNotFoundError:
        send_error_response(client_socket, 404, "File Not Found")

def handle_login(client_socket, post_params):
    """
    Проверяет логин и пароль, отправляет соответствующий ответ
    """
    login = post_params.get('login', '')
    password = post_params.get('password', '')
    
    print(f"Попытка входа: логин={login}, пароль={password}")
    
    if login == VALID_LOGIN and password == VALID_PASSWORD:
        # Доступ разрешен
        response_body = "<html><body><h1 style='color:green'>Доступ разрешен</h1><p>Добро пожаловать в систему!</p></body></html>"
        status_code = 200
        status_text = "OK"
    else:
        # Доступ запрещен
        response_body = "<html><body><h1 style='color:red'>Заблокировано</h1><p>Неверный логин или пароль</p></body></html>"
        status_code = 403
        status_text = "Forbidden"
    
    response_body_encoded = response_body.encode('utf-8')
    
    # Формируем HTTP-ответ
    response = (
        f"HTTP/1.1 {status_code} {status_text}\r\n"
        f"Content-Type: text/html; charset=utf-8\r\n"
        f"Content-Length: {len(response_body_encoded)}\r\n"
        f"Connection: close\r\n"
        f"\r\n"
    ).encode('utf-8') + response_body_encoded
    
    client_socket.send(response)
    print(f"Отправлен ответ {status_code} для {login}")

def send_error_response(client_socket, code, message):
    """
    Отправляет HTML-страницу с ошибкой
    """
    response_body = f"<html><body><h1>{code} {message}</h1></body></html>"
    response_body_encoded = response_body.encode('utf-8')
    
    response = (
        f"HTTP/1.1 {code} {message}\r\n"
        f"Content-Type: text/html; charset=utf-8\r\n"
        f"Content-Length: {len(response_body_encoded)}\r\n"
        f"Connection: close\r\n"
        f"\r\n"
    ).encode('utf-8') + response_body_encoded
    
    client_socket.send(response)

def start_server():
    """
    Запускает многопоточный HTTP-сервер
    """
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    try:
        server_socket.bind((HOST, PORT))
        server_socket.listen(5)
        print(f"Сервер запущен на http://{HOST}:{PORT}")
        print(f"Учетные данные: {VALID_LOGIN} / {VALID_PASSWORD}")
        print("Ожидание подключений... (Ctrl+C для остановки)")
        
        while True:
            client_socket, client_address = server_socket.accept()
            # Запускаем обработку клиента в отдельном потоке
            start_new_thread(handle_client, (client_socket, client_address))
    
    except KeyboardInterrupt:
        print("\nСервер остановлен пользователем")
    except Exception as e:
        print(f"Ошибка при запуске сервера: {e}")
    finally:
        server_socket.close()

if __name__ == "__main__":
    start_server()