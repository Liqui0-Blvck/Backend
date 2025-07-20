from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from business.models import Business
from accounts.models import CustomUser, Perfil

class DebugUserBusinessView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        user = request.user
        perfil = getattr(user, 'perfil', None)
        
        response_data = {
            'user_id': user.id,
            'user_email': user.email,
            'has_perfil': perfil is not None,
        }
        
        if perfil:
            response_data.update({
                'perfil_id': perfil.id,
                'has_business': perfil.business is not None,
            })
            
            if perfil.business:
                response_data.update({
                    'business_id': perfil.business.id,
                    'business_nombre': perfil.business.nombre,
                    'business_rut': perfil.business.rut,
                })
                
                # Contar usuarios por negocio
                users_in_business = CustomUser.objects.filter(perfil__business=perfil.business).count()
                response_data['users_in_business'] = users_in_business
                
                # Contar perfiles por negocio
                perfiles_in_business = Perfil.objects.filter(business=perfil.business).count()
                response_data['perfiles_in_business'] = perfiles_in_business
        
        return Response(response_data)
