"""
API REST (FastAPI + Firestore)
Colecciones: usuarios, publicaciones, comentarios
Operaciones: CRUD + búsquedas específicas
"""

from datetime import datetime
from typing import Optional

from fastapi import FastAPI
from pydantic import BaseModel

import firebase_admin
from firebase_admin import credentials, firestore

# =========================
# Firebase / Firestore
# =========================
cred = credentials.Certificate("credenciales.json")
firebase_admin.initialize_app(cred) # Prepara la conexion
db = firestore.client() # Cliente para interactuar con Firestore

# =========================
# App + Swagger (ordenado por secciones)
# =========================
app = FastAPI(
    title="Servicio REST Firestore",
    version="1.0.0",
    openapi_tags=[
        {"name": "Health", "description": "Verificación del servicio."},
        {"name": "Usuarios", "description": "CRUD y búsquedas por correo/nombre."},
        {"name": "Publicaciones", "description": "CRUD y búsquedas por título/usuario/fechas."},
        {"name": "Comentarios", "description": "CRUD y búsquedas por usuario/publicación/fechas."},
    ],
)

# =========================
# Modelos
# =========================
class Usuario(BaseModel):
    nombreCompleto: str
    correo: str
    contrasenaHash: str


class Publicacion(BaseModel):
    titulo: str
    texto: str
    fechaHora: datetime
    id_usr: str


class Comentario(BaseModel):
    texto: str
    fechaHora: datetime
    id_usr: str
    id_pub: str


# =========================
# Helpers mínimos
# =========================
def doc_dict(doc):
    data = doc.to_dict() # almacena el contenido del documento
    data["id"] = doc.id 
    return data


def exists(collection: str, doc_id: str) -> bool:
    return db.collection(collection).document(doc_id).get().exists


def user_ids_by_nombre(nombre: str):
    return [u.id for u in db.collection("usuarios").where("nombreCompleto", "==", nombre).stream()]


# =========================
# Health
# =========================
@app.get("/", tags=["Health"], summary="Verificar que la API está activa")
def root():
    return {"mensaje": "API conectada correctamente a Firestore"}


# =========================
# Usuarios
# =========================
@app.post("/usuarios", tags=["Usuarios"], summary="Crear usuario")
def crear_usuario(usuario: Usuario):
    doc_ref = db.collection("usuarios").document()
    doc_ref.set(usuario.model_dump()) # model_dump() convierte el modelo Pydantic
    return {"id": doc_ref.id, "mensaje": "Usuario creado"}


@app.get("/usuarios", tags=["Usuarios"], summary="Obtener usuarios (filtro opcional: correo o nombre)")
def obtener_usuarios(correo: Optional[str] = None, nombre: Optional[str] = None):
    ref = db.collection("usuarios")

    if correo:
        query = ref.where("correo", "==", correo)
    elif nombre:
        query = ref.where("nombreCompleto", "==", nombre)
    else:
        query = ref

    return [doc_dict(d) for d in query.stream()]


@app.get("/usuarios/{user_id}", tags=["Usuarios"], summary="Obtener usuario por ID")
def obtener_usuario(user_id: str):
    doc = db.collection("usuarios").document(user_id).get() # obtiene el documento con el ID especificado
    if not doc.exists:
        return {"error": "Usuario no encontrado"}
    return doc_dict(doc)


@app.put("/usuarios/{user_id}", tags=["Usuarios"], summary="Actualizar usuario por ID")
def actualizar_usuario(user_id: str, usuario: Usuario):
    doc_ref = db.collection("usuarios").document(user_id)
    if not doc_ref.get().exists:
        return {"error": "Usuario no encontrado"}

    doc_ref.update(usuario.model_dump()) # Pydantic convierte el modelo a un diccionario con model_dump()
    return {"mensaje": "Usuario actualizado"}


@app.delete("/usuarios/{user_id}", tags=["Usuarios"], summary="Eliminar usuario por ID")
def eliminar_usuario(user_id: str):
    doc_ref = db.collection("usuarios").document(user_id)
    if not doc_ref.get().exists:
        return {"error": "Usuario no encontrado"}

    doc_ref.delete()
    return {"mensaje": "Usuario eliminado"}


# =========================
# Publicaciones
# =========================
@app.post("/publicaciones", tags=["Publicaciones"], summary="Crear publicación")
def crear_publicacion(publicacion: Publicacion):
    if not exists("usuarios", publicacion.id_usr):
        return {"error": "Usuario no existe"}

    doc_ref = db.collection("publicaciones").document()
    doc_ref.set(publicacion.model_dump())
    return {"id": doc_ref.id, "mensaje": "Publicación creada"}


@app.get("/publicaciones", tags=["Publicaciones"], summary="Obtener publicaciones (filtros: titulo, usuario, desde, hasta)")
def obtener_publicaciones(
    titulo: Optional[str] = None,
    usuario: Optional[str] = None,
    desde: Optional[datetime] = None,
    hasta: Optional[datetime] = None,
):
    query = db.collection("publicaciones") # referencia a la colección de publicaciones

    if titulo:
        query = query.where("titulo", "==", titulo)

    if desde:
        query = query.where("fechaHora", ">=", desde)
    if hasta:
        query = query.where("fechaHora", "<=", hasta)

    if usuario:
        ids = user_ids_by_nombre(usuario)
        if not ids:
            return []
        query = query.where("id_usr", "in", ids) # Traer publicaciones de todos los usuarios que coincidan con el nombre

    return [doc_dict(d) for d in query.stream()]


@app.get("/publicaciones/{pub_id}", tags=["Publicaciones"], summary="Obtener publicación por ID")
def obtener_publicacion(pub_id: str):
    doc = db.collection("publicaciones").document(pub_id).get()
    if not doc.exists:
        return {"error": "Publicación no encontrada"}
    return doc_dict(doc)


@app.put("/publicaciones/{pub_id}", tags=["Publicaciones"], summary="Actualizar publicación por ID")
def actualizar_publicacion(pub_id: str, publicacion: Publicacion):
    doc_ref = db.collection("publicaciones").document(pub_id)
    if not doc_ref.get().exists:
        return {"error": "Publicación no encontrada"}

    if not exists("usuarios", publicacion.id_usr):
        return {"error": "Usuario no existe"}

    doc_ref.update(publicacion.model_dump())
    return {"mensaje": "Publicación actualizada"}


@app.delete("/publicaciones/{pub_id}", tags=["Publicaciones"], summary="Eliminar publicación por ID")
def eliminar_publicacion(pub_id: str):
    doc_ref = db.collection("publicaciones").document(pub_id)
    if not doc_ref.get().exists:
        return {"error": "Publicación no encontrada"}

    doc_ref.delete()
    return {"mensaje": "Publicación eliminada"}


# =========================
# Comentarios
# =========================
@app.post("/comentarios", tags=["Comentarios"], summary="Crear comentario")
def crear_comentario(comentario: Comentario):
    if not exists("usuarios", comentario.id_usr):
        return {"error": "Usuario no existe"}
    if not exists("publicaciones", comentario.id_pub):
        return {"error": "Publicación no existe"}

    doc_ref = db.collection("comentarios").document()
    doc_ref.set(comentario.model_dump())
    return {"id": doc_ref.id, "mensaje": "Comentario creado"}


@app.get("/comentarios", tags=["Comentarios"], summary="Obtener comentarios (filtros: usuario, publicacion_id, desde, hasta)")
def obtener_comentarios(
    usuario: Optional[str] = None,
    publicacion_id: Optional[str] = None,
    desde: Optional[datetime] = None,
    hasta: Optional[datetime] = None,
):
    query = db.collection("comentarios")

    if publicacion_id:
        query = query.where("id_pub", "==", publicacion_id)

    if desde:
        query = query.where("fechaHora", ">=", desde)
    if hasta:
        query = query.where("fechaHora", "<=", hasta)

    if usuario:
        ids = user_ids_by_nombre(usuario)
        if not ids:
            return []
        query = query.where("id_usr", "in", ids)

    return [doc_dict(d) for d in query.stream()]


@app.get("/comentarios/{com_id}", tags=["Comentarios"], summary="Obtener comentario por ID")
def obtener_comentario(com_id: str):
    doc = db.collection("comentarios").document(com_id).get()
    if not doc.exists:
        return {"error": "Comentario no encontrado"}
    return doc_dict(doc)


@app.put("/comentarios/{com_id}", tags=["Comentarios"], summary="Actualizar comentario por ID")
def actualizar_comentario(com_id: str, comentario: Comentario):
    doc_ref = db.collection("comentarios").document(com_id)
    if not doc_ref.get().exists:
        return {"error": "Comentario no encontrado"}

    if not exists("usuarios", comentario.id_usr):
        return {"error": "Usuario no existe"}
    if not exists("publicaciones", comentario.id_pub):
        return {"error": "Publicación no existe"}

    doc_ref.update(comentario.model_dump())
    return {"mensaje": "Comentario actualizado"}


@app.delete("/comentarios/{com_id}", tags=["Comentarios"], summary="Eliminar comentario por ID")
def eliminar_comentario(com_id: str):
    doc_ref = db.collection("comentarios").document(com_id)
    if not doc_ref.get().exists:
        return {"error": "Comentario no encontrado"}

    doc_ref.delete()
    return {"mensaje": "Comentario eliminado"}