ARG REGISTRY
FROM ${REGISTRY}nginx:alpine

# Copy the Nginx configuration file
COPY nginx.conf /etc/nginx/nginx.conf

# Create directory for error pages
RUN mkdir -p /usr/share/nginx/html

# Create basic error page
RUN echo '<html><body><h1>Error</h1><p>Something went wrong.</p></body></html>' > /usr/share/nginx/html/50x.html

WORKDIR /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
