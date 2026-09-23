"""Hablar cifrado con un relé de certificado propio, sin apagar la verificación.

Un relé dentro de la misma red suele tener un certificado autofirmado, y el
envío de Django se niega a hablar con él. La salida habitual es apagar la
verificación. Esto la cambia por fiarse de **ese** certificado y de ningún otro.

Se prueba contra un servidor TLS de verdad, en un hilo, con dos certificados
recién generados: el del relé y otro cualquiera.
"""

from __future__ import annotations

import datetime
import socket
import ssl
import threading

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID
from django.test import override_settings

from apps.common.mail import SMTPBackend


def _certificado(tmp_path, nombre):
    clave = ec.generate_private_key(ec.SECP256R1())
    sujeto = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, nombre)])
    ahora = datetime.datetime.now(datetime.UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(sujeto)
        .issuer_name(sujeto)
        .public_key(clave.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(ahora - datetime.timedelta(days=1))
        .not_valid_after(ahora + datetime.timedelta(days=1))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(clave, hashes.SHA256())
    )
    ruta_cert = tmp_path / f"{nombre}.pem"
    ruta_clave = tmp_path / f"{nombre}.key"
    ruta_cert.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    ruta_clave.write_bytes(
        clave.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    return ruta_cert, ruta_clave


@pytest.fixture
def rele(tmp_path):
    """Un servidor TLS en 127.0.0.1 con el certificado de «rele.interno»."""
    cert, clave = _certificado(tmp_path, "rele.interno")
    contexto = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    contexto.load_cert_chain(cert, clave)
    escucha = socket.create_server(("127.0.0.1", 0))
    puerto = escucha.getsockname()[1]

    def atender():
        escucha.settimeout(5)
        try:
            conexion, _ = escucha.accept()
            with contexto.wrap_socket(conexion, server_side=True) as tls:
                tls.recv(1)
        except OSError, ssl.SSLError:
            pass

    hilo = threading.Thread(target=atender, daemon=True)
    hilo.start()
    yield {"puerto": puerto, "cert": cert, "otro": _certificado(tmp_path, "otro")[0]}
    escucha.close()


def _conectar(puerto, contexto):
    with socket.create_connection(("127.0.0.1", puerto), timeout=5) as crudo:
        with contexto.wrap_socket(crudo, server_hostname="127.0.0.1"):
            return True


def test_sin_ajustes_es_el_de_django_y_rechaza_el_autofirmado(rele):
    with override_settings(EMAIL_SSL_CAFILE=""):
        contexto = SMTPBackend().ssl_context
    with pytest.raises(ssl.SSLCertVerificationError):
        _conectar(rele["puerto"], contexto)


def test_con_su_certificado_y_sin_mirar_el_nombre_habla(rele):
    """Al relé se llega por su dirección interna, que su certificado no nombra."""
    with override_settings(EMAIL_SSL_CAFILE=str(rele["cert"]), EMAIL_SSL_CHECK_HOSTNAME=False):
        contexto = SMTPBackend().ssl_context
    assert contexto.verify_mode == ssl.CERT_REQUIRED, "la verificación sigue encendida"
    assert _conectar(rele["puerto"], contexto)


def test_con_otro_certificado_no_habla(rele):
    """Lo que importa: fiarse de uno no es fiarse de cualquiera."""
    with override_settings(EMAIL_SSL_CAFILE=str(rele["otro"]), EMAIL_SSL_CHECK_HOSTNAME=False):
        contexto = SMTPBackend().ssl_context
    with pytest.raises(ssl.SSLCertVerificationError):
        _conectar(rele["puerto"], contexto)


def test_mirando_el_nombre_no_basta_con_el_certificado(rele):
    with override_settings(EMAIL_SSL_CAFILE=str(rele["cert"]), EMAIL_SSL_CHECK_HOSTNAME=True):
        contexto = SMTPBackend().ssl_context
    with pytest.raises(ssl.SSLCertVerificationError):
        _conectar(rele["puerto"], contexto)
