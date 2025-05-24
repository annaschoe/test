"""
Diagnostic tool for checking Flask application status
"""
import os
import sys
import psutil
import logging
from flask import Flask, jsonify, request

def get_app_stats():
    """Get basic system and process statistics"""
    process = psutil.Process(os.getpid())
    
    stats = {
        "process": {
            "memory_usage_mb": process.memory_info().rss / (1024 * 1024),
            "cpu_percent": process.cpu_percent(interval=0.1),
            "threads": process.num_threads(),
            "open_files": len(process.open_files()),
            "connections": len(process.connections()),
        },
        "system": {
            "cpu_percent": psutil.cpu_percent(interval=0.1),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_usage_percent": psutil.disk_usage('/').percent,
        }
    }
    
    return stats

def register_diagnostic_routes(app):
    """Register diagnostic routes with the Flask app"""
    
    @app.route('/status')
    def api_status():
        """Basic API health check endpoint"""
        return jsonify({"status": "ok"})
    
    @app.route('/diagnostics')
    def diagnostics():
        """Detailed diagnostics endpoint"""
        if app.debug:
            stats = get_app_stats()
            routes = [str(rule) for rule in app.url_map.iter_rules()]
            
            # Check for request overload
            is_overloaded = stats['system']['cpu_percent'] > 80 or stats['system']['memory_percent'] > 90
            
            diagnostics_data = {
                "app": {
                    "version": getattr(app, "version", "unknown"),
                    "debug_mode": app.debug,
                    "testing_mode": app.testing,
                    "registered_routes": len(routes),
                    "route_list": routes
                },
                "stats": stats,
                "potential_issues": {
                    "overloaded": is_overloaded,
                    "high_memory_usage": stats['process']['memory_usage_mb'] > 500,  # Flag if using over 500MB
                    "high_cpu_usage": stats['process']['cpu_percent'] > 70  # Flag if using over 70% CPU
                }
            }
            return jsonify(diagnostics_data)
        
        return jsonify({"error": "Diagnostics only available in debug mode"})

    return app
