
from Products.NuxCPS3.ElementsMapping import ElementsMapping

class DummyRequest:
    def __init__(self):
        self.other = {}
        self.SESSION = {}

def getElements(setter):
    request = DummyRequest()
    return ElementsMapping(request, setter)
