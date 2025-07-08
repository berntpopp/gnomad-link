# Improve Error Handling and HTTP Status Codes to Follow Industry Standards

## Summary
The current error handling implementation returns 502 Bad Gateway for client validation errors, which should instead return 400 Bad Request according to HTTP standards. Additionally, the system needs better handling of unexpected errors and more informative error messages.

## Current Behavior
- Client validation errors (e.g., invalid parameters, malformed requests) return 502 Bad Gateway
- Error messages may not provide sufficient detail for debugging
- Unexpected errors might not be properly caught and handled
- No consistent error response format across all endpoints

## Expected Behavior
According to industry standards and REST API best practices:
- **400 Bad Request**: Client errors (invalid input, missing required fields, validation failures)
- **404 Not Found**: Resource not found
- **422 Unprocessable Entity**: Valid request format but semantic errors
- **500 Internal Server Error**: Unexpected server errors
- **502 Bad Gateway**: Only when the upstream service (gnomAD GraphQL) is unreachable
- **503 Service Unavailable**: When the service is temporarily unavailable
- **504 Gateway Timeout**: When upstream service times out

## Proposed Solution

### 1. Error Response Format
Implement a consistent error response structure:
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid variant format",
    "details": {
      "field": "variant_id",
      "expected": "chr-pos-ref-alt format",
      "received": "invalid-format"
    },
    "request_id": "unique-request-id",
    "timestamp": "2025-01-08T12:00:00Z"
  }
}
```

### 2. Error Categories and Status Codes

#### Client Errors (4xx)
- **400 Bad Request**
  - Invalid request format
  - Missing required parameters
  - Invalid parameter types
  - Malformed JSON

- **404 Not Found**
  - Gene not found
  - Variant not found
  - Transcript not found

- **422 Unprocessable Entity**
  - Valid format but invalid values
  - Business logic validation failures

#### Server Errors (5xx)
- **500 Internal Server Error**
  - Unexpected exceptions
  - Database connection failures
  - Internal service failures

- **502 Bad Gateway**
  - gnomAD GraphQL API unreachable
  - Network failures to upstream

- **504 Gateway Timeout**
  - gnomAD GraphQL API timeout

### 3. Implementation Tasks

- [ ] Create custom exception classes for different error types:
  ```python
  class ValidationError(Exception): pass
  class ResourceNotFoundError(Exception): pass
  class UpstreamServiceError(Exception): pass
  ```

- [ ] Implement global exception handlers in FastAPI:
  ```python
  @app.exception_handler(ValidationError)
  async def validation_exception_handler(request, exc):
      return JSONResponse(
          status_code=400,
          content={"error": {...}}
      )
  ```

- [ ] Update all endpoints to raise appropriate exceptions

- [ ] Add request ID middleware for error tracking

- [ ] Implement comprehensive error logging with context

- [ ] Add retry logic for transient upstream failures

- [ ] Create error documentation for API consumers

### 4. Specific Areas to Address

1. **`base_client.py`**: 
   - Distinguish between network errors and GraphQL errors
   - Map GraphQL errors to appropriate HTTP status codes

2. **Route handlers**:
   - Validate input parameters before processing
   - Return 404 when resources not found instead of 502

3. **Service layer**:
   - Wrap external calls with proper error handling
   - Add circuit breaker pattern for upstream failures

### 5. Testing Requirements

- [ ] Unit tests for each error scenario
- [ ] Integration tests for error propagation
- [ ] Test error message clarity and usefulness
- [ ] Verify correct status codes for each error type
- [ ] Test error logging and monitoring integration

## Benefits
- Better developer experience with clear, actionable error messages
- Easier debugging with consistent error formats
- Proper HTTP semantics for API consumers
- Better monitoring and alerting capabilities
- Improved system reliability through proper error handling

## References
- [HTTP Status Codes - MDN](https://developer.mozilla.org/en-US/docs/Web/HTTP/Status)
- [REST API Error Handling Best Practices](https://blog.restcase.com/rest-api-error-handling-best-practices/)
- [RFC 7807 - Problem Details for HTTP APIs](https://datatracker.ietf.org/doc/html/rfc7807)

## Priority
High - This affects API usability and production readiness

## Labels
- enhancement
- bug
- api
- error-handling
- breaking-change (if error response format changes)