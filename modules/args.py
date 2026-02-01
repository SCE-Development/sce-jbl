import argparse

def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--host',
        help='Host address to run the server on',
        default='0.0.0.0',
    )
    parser.add_argument(
        '--port',
        help='Port number to run the server on',
        type=int,
        default=6969,
    )
    parser.add_argument(
        '--output-dir',
        help='Directory to save downloaded songs',
        default='videos',
    )
    parser.add_argument(
        '--jbl-mac-address',
        help='MAC address of the JBL speaker',
        required=True,
    )
    return parser.parse_args()