"""Unit tests for dependency injection container."""
import pytest
from app.core.container import Container


class TestContainer:
    """Test DI container functionality."""
    
    def test_register_and_resolve(self):
        """Test basic registration and resolution."""
        container = Container()
        
        # Register a simple factory
        container.register("test_key", lambda: "test_value")
        
        # Resolve and check value
        result = container.resolve("test_key")
        assert result == "test_value"
    
    def test_register_class_instance(self):
        """Test registering class instances."""
        container = Container()
        
        class TestClass:
            def __init__(self, value):
                self.value = value
        
        # Register factory that creates instance
        container.register(TestClass, lambda: TestClass(42))
        
        # Resolve and check
        instance = container.resolve(TestClass)
        assert isinstance(instance, TestClass)
        assert instance.value == 42
    
    def test_resolve_unregistered_raises_error(self):
        """Test that resolving unregistered key raises KeyError."""
        container = Container()
        
        with pytest.raises(KeyError, match="No factory registered"):
            container.resolve("nonexistent_key")
    
    def test_factory_called_each_time(self):
        """Test that factory is called on each resolve (not singleton)."""
        container = Container()
        counter = {"value": 0}
        
        def factory():
            counter["value"] += 1
            return counter["value"]
        
        container.register("counter", factory)
        
        # Resolve twice
        first = container.resolve("counter")
        second = container.resolve("counter")
        
        # Should get different values
        assert first == 1
        assert second == 2
    
    def test_register_with_dependencies(self):
        """Test registering factories with dependencies."""
        container = Container()
        
        class Database:
            pass
        
        class Service:
            def __init__(self, db):
                self.db = db
        
        # Register database
        container.register(Database, lambda: Database())
        
        # Register service with database dependency
        container.register(Service, lambda: Service(container.resolve(Database)))
        
        # Resolve service
        service = container.resolve(Service)
        assert isinstance(service, Service)
        assert isinstance(service.db, Database)
