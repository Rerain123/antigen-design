import copy
import pytest
from scripts import publish_esmfold2_backend_control as publication


def image():
    return {'Id':publication.EXPECTED_INDEX}, {'Descriptor':{'digest':publication.EXPECTED_PLATFORM},'Os':'linux','Architecture':'amd64'}


def test_registered_image():
    publication.validate_image(*image())
    assert publication.publisher.POD=='antigen-esmfold2-backend-relay-r03'
    assert publication.OUT.name=='esmfold2-backend-publish-20260917-r03'


@pytest.mark.parametrize('damage',['index','platform','os','arch'])
def test_changed_image_refused(damage):
    native,platform=copy.deepcopy(image())
    if damage=='index':native['Id']='sha256:'+'a'*64
    elif damage=='platform':platform['Descriptor']['digest']='sha256:'+'b'*64
    elif damage=='os':platform['Os']='windows'
    else:platform['Architecture']='arm64'
    with pytest.raises(ValueError):publication.validate_image(native,platform)
