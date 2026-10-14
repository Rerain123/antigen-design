from .typing import List, Optional, TypedDict


class SensitivityLabelDict(TypedDict):
    uuid: str
    name: str


class SensitivityLabelCategorySummaryDict(TypedDict):
    uuid: str
    name: str


class SensitivityLabelCategoryDict(SensitivityLabelCategorySummaryDict):
    labels: List[SensitivityLabelDict]
    learn_more_link: Optional[str]


class ResultSensitivityLabelDict(TypedDict):
    uuid: str
    label: SensitivityLabelDict
    category: SensitivityLabelCategorySummaryDict
