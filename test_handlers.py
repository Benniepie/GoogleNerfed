import urllib.request
import urllib.error

# Build an opener that only has HTTP and HTTPS handlers, explicitly stripping out FileHandler
opener = urllib.request.OpenerDirector()
for handler_class in [urllib.request.HTTPHandler, urllib.request.HTTPSHandler, urllib.request.HTTPDefaultErrorHandler, urllib.request.HTTPRedirectHandler, urllib.request.HTTPErrorProcessor]:
    opener.add_handler(handler_class())

try:
    opener.open("file:///etc/passwd")
    print("Failed to block file")
except Exception as e:
    print(f"Blocked file: {type(e)} {e}")
