"""Compatibility regressions for transitive security dependency upgrades."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs7
from gql import gql
from gql.transport.aiohttp import AIOHTTPTransport


def test_pkcs7_enveloped_data_round_trip_uses_the_patched_decrypt_surface() -> None:
    """The indirect cryptography upgrade must retain PKCS#7 decrypt behavior."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name(
        [x509.NameAttribute(x509.NameOID.COMMON_NAME, "gnomad-link dependency regression")]
    )
    now = datetime.now(UTC)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(days=1))
        .sign(private_key, hashes.SHA256())
    )
    payload = b"gnomad-link dependency compatibility\x00"
    envelope = (
        pkcs7.PKCS7EnvelopeBuilder()
        .set_data(payload)
        .add_recipient(certificate)
        .encrypt(serialization.Encoding.DER, [pkcs7.PKCS7Options.Binary])
    )

    decrypted = pkcs7.pkcs7_decrypt_der(envelope, certificate, private_key, [])

    assert decrypted == payload


@pytest.mark.asyncio
async def test_gql_aiohttp_transport_parses_a_valid_chunked_response() -> None:
    """Exercise the real chunked-response parser used by the gnomAD GraphQL client."""

    async def handle_request(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        await reader.readuntil(b"\r\n\r\n")
        body = b'{"data":{"viewer":"ok"}}'
        writer.write(
            b"HTTP/1.1 200 OK\r\n"
            b"Content-Type: application/json\r\n"
            b"Transfer-Encoding: chunked\r\n"
            b"Connection: close\r\n\r\n" + f"{len(body):X}\r\n".encode() + body + b"\r\n0\r\n\r\n"
        )
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    server = await asyncio.start_server(handle_request, "127.0.0.1", 0)
    assert server.sockets
    port = server.sockets[0].getsockname()[1]
    transport = AIOHTTPTransport(url=f"http://127.0.0.1:{port}/graphql")
    await transport.connect()
    try:
        result = await transport.execute(gql("query { viewer }"))
    finally:
        await transport.close()
        server.close()
        await server.wait_closed()

    assert result.errors is None
    assert result.data == {"viewer": "ok"}
