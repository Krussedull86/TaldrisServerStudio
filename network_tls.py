"""Portable CA bundle plus OS roots. Certificate and hostname checks stay enabled."""
import ssl
import certifi
from urllib.error import URLError

def tls_context():
    context=ssl.create_default_context()
    # Add the bundled Mozilla roots; keep Windows/system roots for managed networks.
    context.load_verify_locations(cafile=certifi.where())
    return context

def network_message(error):
    reason=getattr(error,'reason',error)
    if isinstance(reason,ssl.SSLCertVerificationError) or 'CERTIFICATE_VERIFY_FAILED' in str(reason):
        return ('Kunne ikke bekrefte nettsidens sertifikat. Kontroller dato/klokkeslett og Windows-oppdateringer. '
                'Hvis nettverket bruker sertifikatkontroll, må det riktige rotsertifikatet være klarert i Windows. '
                'Sertifikatkontroll er fortsatt aktiv.')
    return str(error)
