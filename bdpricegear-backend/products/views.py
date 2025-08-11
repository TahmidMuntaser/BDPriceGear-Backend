from rest_framework.decorators import api_view
from rest_framework.response import Response

@api_view(['GET'])
def price_comparison(request):
    
    # placeholder endpoint
    return Response({
        "status": "success", 
        "message": "Price comparison data will be returned here."
    }) 