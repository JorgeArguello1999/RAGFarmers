# Redis Dockerfile 
FROM redis:7.2

# Define environment variables for Redis configuration
ENV REDIS_PASSWORD=devpass123
ENV REDIS_PORT=6379

# Copy the Redis configuration file
COPY database/redis.conf /usr/local/etc/redis/redis.conf

# Expose the Redis port
EXPOSE ${REDIS_PORT}

# Run Redis server with the specified configuration
CMD ["redis-server", "/usr/local/etc/redis/redis.conf"]
