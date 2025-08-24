import requests

# Reemplaza esto con tu token de acceso válido
ACCESS_TOKEN = "TU_ACCESS_TOKEN"

# Función para obtener las publicaciones de un vendedor
def get_seller_items(seller_id):
    """
    Obtiene las publicaciones de un vendedor específico.
    """
    url = f"https://api.mercadolibre.com/sites/MLA/search?seller_id={seller_id}"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error al obtener publicaciones del vendedor {seller_id}: {response.status_code}")
        return {}

# Función para obtener detalles completos de una publicación
def get_item_details(item_id):
    """
    Obtiene los detalles completos de una publicación específica.
    Incluye el número de vendidos.
    """
    url = f"https://api.mercadolibre.com/items/{item_id}"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error al obtener detalles de la publicación {item_id}: {response.status_code}")
        return {}

# Función para obtener las vistas de los últimos 7 días
def get_item_visits(item_id):
    """
    Obtiene las vistas de una publicación en los últimos 7 días.
    """
    url = f"https://api.mercadolibre.com/items/{item_id}/visits/time_window?last=7"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error al obtener estadísticas de vistas para la publicación {item_id}: {response.status_code}")
        return {}

# Función principal
def main():
    """
    Función principal para listar publicaciones y obtener detalles.
    """
    # Solicitar el ID del vendedor
    seller_id = input("Introduce el ID del vendedor que deseas analizar: ")
    
    # Obtener publicaciones del vendedor
    seller_items = get_seller_items(seller_id)
    
    if "results" in seller_items and seller_items["results"]:
        print(f"\nPublicaciones del vendedor {seller_id}:")
        for idx, item in enumerate(seller_items["results"][:20], 1):  # Mostrar las primeras 20 publicaciones
            print(f"{idx}. ID: {item['id']}, Título: {item['title']}, Precio: {item['price']} {item['currency_id']}")
    else:
        print("No se encontraron publicaciones para este vendedor.")
        return
    
    # Solicitar el ID de una publicación para ver más detalles
    item_id = input("\nIntroduce el ID de una publicación para obtener detalles: ")
    item_details = get_item_details(item_id)
    item_visits = get_item_visits(item_id)
    
    # Mostrar los detalles de la publicación
    if item_details:
        print("\nDetalles de la publicación seleccionada:")
        print(f"Título: {item_details.get('title', 'N/A')}")
        print(f"Precio: {item_details.get('price', 'N/A')} {item_details.get('currency_id', 'N/A')}")
        print(f"Cantidad vendida: {item_details.get('sold_quantity', 'N/A')}")
    
    if item_visits:
        print(f"Vistas en los últimos 7 días: {item_visits.get('total_visits', 'N/A')}")
    else:
        print("No se encontraron estadísticas de vistas para esta publicación.")

# Ejecutar la función principal
if __name__ == "__main__":
    main()

