import argparse
import json
import os
from pathlib import Path
import time
import urllib.error
import urllib.request
import uuid
import zipfile
from vendor_catalog import files_for_side, load_catalog, safe_path, safe_url, verify_artifact


class ApprovedRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, new_url):
        safe_url(new_url)
        return super().redirect_request(request, response, code, message, headers, new_url)


def fetch(entry, root, opener=None):
    target = Path(root) / safe_path(entry['path'])
    if target.exists():
        return {**verify_artifact(entry, target), 'reused': True}
    if entry['delivery'] == 'manual':
        raise ValueError('Install this pinned vendor from its official page: ' + entry['filePageUrl'])
    target.parent.mkdir(parents=True, exist_ok=True)
    opener = opener or urllib.request.build_opener(ApprovedRedirects())
    failures = []
    for url in entry['officialUrls']:
        safe_url(url)
        temporary = target.with_name(target.name + '.' + uuid.uuid4().hex + '.part')
        try:
            received, started = 0, time.monotonic()
            request = urllib.request.Request(url, headers={'User-Agent': 'RV-vendor-catalog/1', 'Accept': 'application/octet-stream'})
            with opener.open(request, timeout=30) as response, temporary.open('xb') as stream:
                safe_url(response.geturl())
                length = response.headers.get('Content-Length')
                if length is not None and int(length) != entry['size']:
                    raise ValueError('Official response size differs from the pin')
                while data := response.read(1024 * 1024):
                    received += len(data)
                    if received > entry['size'] or time.monotonic() - started > 600:
                        raise ValueError('Vendor download exceeds its bound')
                    stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            result = verify_artifact(entry, temporary)
            if target.exists():
                result = verify_artifact(entry, target)
            else:
                temporary.rename(target)
            return {**result, 'reused': False, 'officialUrl': url}
        except (OSError, ValueError, zipfile.BadZipFile, KeyError, urllib.error.URLError) as error:
            failures.append(type(error).__name__)
        finally:
            temporary.unlink(missing_ok=True)
    raise ValueError('Pinned official vendor download failed: ' + entry['id'] + ' (' + ', '.join(failures) + ')')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--catalog', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--side', choices=['client', 'server'], required=True)
    args = parser.parse_args()
    catalog = load_catalog(args.catalog)
    report = [fetch(entry, args.output) for entry in files_for_side(catalog, args.side)]
    print(json.dumps({'side': args.side, 'files': report, 'publicationApproved': False}))


if __name__ == '__main__':
    main()
