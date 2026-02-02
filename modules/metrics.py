import enum

import prometheus_client


class Metrics(enum.Enum):

    ENDPOINT_HITS = (
        'endpoint_hits',
        'Count of each HTTP Response code',
        prometheus_client.Counter,
        ['path', 'code']
    )

    JBL_LAST_CONNECTED = (
        'jbl_last_connected',
        'Timestamp of the last successful connection to the JBL speaker',
        prometheus_client.Gauge,
    )

    BLUETOOTH_ERROR = (
        'bluetooth_error',
        'Gauge of Bluetooth connection errors',
        prometheus_client.Gauge,
    )

    def __init__(self, title, description, prometheus_type, label=()):
        self.title = title
        self.description = description
        self.prometheus_type = prometheus_type
        self.labels = label

class MetricsHandler:
    _instance = None

    def __init__(self):
        raise RuntimeError('Call MetricsHandler.instance() instead')
    
    def init(self) -> None:
        for metric in Metrics:
            setattr(
                self,
                metric.title,
                metric.prometheus_type(
                    metric.title, metric.description, labelnames=metric.labels
                )
            )
    
    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = cls.__new__(cls)
            cls.init(cls)
        return cls._instance
