"""
Session cache management for FastF1 sessions.
Implements LRU cache with thread-safe operations.
"""
from collections import OrderedDict
from threading import Lock, Event


class SessionCache:
    """
    Thread-safe LRU cache for FastF1 session objects.
    """
    
    def __init__(self, max_size: int = 4):
        """
        Initialize session cache.
        
        Args:
            max_size: Maximum number of sessions to cache
        """
        self._cache = OrderedDict()
        self._lock = Lock()
        self._max_size = max_size
        self._loading_events = {}
    
    def get(self, key):
        """
        Get session from cache if available.
        
        Args:
            key: Cache key (tuple of season, event, session_code)
            
        Returns:
            Cached session or None if not found
        """
        with self._lock:
            cached_session = self._cache.get(key)
            if cached_session is not None:
                self._cache.move_to_end(key)
                return cached_session
            return None
    
    def set(self, key, session):
        """
        Add session to cache, evicting oldest if at capacity.
        
        Args:
            key: Cache key
            session: FastF1 session object
        """
        with self._lock:
            self._cache[key] = session
            self._cache.move_to_end(key)
            while len(self._cache) > self._max_size:
                evicted_key, _ = self._cache.popitem(last=False)
                print(f"[CACHE] session evicted {evicted_key}", flush=True)
    
    def get_or_create_loading_event(self, key):
        """
        Get existing loading event or create new one.
        
        Args:
            key: Cache key
            
        Returns:
            Tuple of (event, is_loader) where is_loader is True if this
            caller should perform the load
        """
        with self._lock:
            if key in self._loading_events:
                return self._loading_events[key], False
            else:
                wait_event = Event()
                self._loading_events[key] = wait_event
                return wait_event, True
    
    def remove_loading_event(self, key):
        """
        Remove loading event and signal waiting threads.
        
        Args:
            key: Cache key
        """
        with self._lock:
            event = self._loading_events.pop(key, None)
            if event is not None:
                event.set()
    
    def hit(self, key):
        """
        Log cache hit.
        
        Args:
            key: Cache key
        """
        print(f"[CACHE] session hit {key}", flush=True)
    
    def miss(self, key):
        """
        Log cache miss.
        
        Args:
            key: Cache key
        """
        print(f"[CACHE] session miss {key}, loading with telemetry", flush=True)
    
    def wait(self, key):
        """
        Log cache wait.
        
        Args:
            key: Cache key
        """
        print(f"[CACHE] session wait {key}", flush=True)
