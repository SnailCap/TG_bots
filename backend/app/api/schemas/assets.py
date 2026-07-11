from .common import ApiModel


class AssetPathResponse(ApiModel):
    path: str


class RenameAssetRequest(ApiModel):
    path: str
    new_path: str

