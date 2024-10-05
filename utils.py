from main import API_URL
import requests

# GraphQL API client
def graphql_query(query):
    response = requests.post(API_URL, json={"query": query})
    response.raise_for_status()
    return response.json()
