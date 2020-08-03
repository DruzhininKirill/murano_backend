from rest_framework import viewsets
from gamification.serializers import UserSerializer, TransactionSerializer, CategorySerializer, \
    UserCreateSerializer, FeedbackMessageSerializer, UserFIOSerializer, CreateFeedbackMessageSerializer, \
    ProductSerializer, \
    OrderProductSerializer, OrderCreateSerializer, OrderSerializer, OrderStatusSerializer, UserBadgeSerializer
from django.contrib.auth import get_user_model
from .models import Category, Transaction, FeedbackMessage, Product, Order, OrderProduct, UserBadge
from rest_framework.response import Response
from rest_framework import status
from django.http import HttpResponseBadRequest, HttpResponse
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from .permissions import IsStaffOrReadOnly, IsOwnerOrReadOnly, IsStaff
from django.contrib.auth.hashers import make_password, PBKDF2SHA1PasswordHasher
from django.core import mail
import xlwt, os, base64
from django.shortcuts import render
from django.utils import timezone

from rest_framework.decorators import api_view, permission_classes, action

from rest_framework.throttling import UserRateThrottle
from django.core.files.base import ContentFile

class OncePerDayUserThrottle(UserRateThrottle):
    rate = '1/day'


class UserViewSet(viewsets.ModelViewSet):
    queryset = get_user_model().objects.all()
    serializer_class = UserSerializer

    def get_permissions(self):

        if (self.action == 'list') or (self.action == 'update'):
            permission_classes = [IsOwnerOrReadOnly]
        else:
            if (self.action == 'add_interest') or (self.action == 'interests'):
                permission_classes =[IsAuthenticated]
            else:
                permission_classes = [IsAdminUser]
        return [permission() for permission in permission_classes]

    def create(self, request, *args, **kwargs):
        data = request.data
        data['password'] = make_password(data['password'])
        serializer = UserCreateSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save();
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def partial_update(self, request, *args, **kwargs):
        data = request.data
        if 'password' in data:
            data['password'] = make_password(data['password'])
        # if 'image' in data:
        #     m = get_user_model()
        #     m.image = request.FILES['image']
        #     m.save()

        serializer = UserCreateSerializer(request.user, data=request.data, partial=True, context={"request": request})
        if serializer.is_valid():
            instance = self.get_object()
            serializer.update(instance, serializer.validated_data)
            response = serializer.to_representation(instance)
            # serialized_object = UserSerializer('json', [get_user_model(),])

            return Response(response, status=status.HTTP_202_ACCEPTED)
            # return Response(serializer.data, status=status.HTTP_202_ACCEPTED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


    @api_view(['POST'])
    @permission_classes([IsAdminUser])
    def month_update (request, format=None):
        users = get_user_model().objects.all()
        for user in users:
            user.share_points = '10'
            user.save()

        return Response('success', status=status.HTTP_202_ACCEPTED)

    # @permission_classes([IsAuthenticated])
    @action(methods=['post'], detail=False)
    def add_interest(self, request):
        print(request)
        data = request.data
        data['user'] = request.user.pk
        try:
            b = UserBadge.objects.get(user=data['user'], badge=data['badge'])
        except UserBadge.DoesNotExist:
            b = None

        if b == None:
            serializer = UserBadgeSerializer(data=data)
            if serializer.is_valid():
                serializer.save()
            # obj, created = UserBadge.objects.get_or_create(user=serializer.validated_data['user'] ,
            #                                                badge=serializer.validated_data['badge'] )
                return Response('added', status=status.HTTP_202_ACCEPTED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        else:
            b.delete()
            return Response('excluded', status=status.HTTP_202_ACCEPTED)

    @action(methods=['get'], detail=True)
    def interests (self, request, pk=None):


        obj = get_user_model().objects.get(pk=pk)
        queryset = UserBadge.objects.filter(user=obj).values('badge')
        interests = []
        for i in queryset:
            interests.append(i['badge'])

        return Response(interests)
        #
        # return Response('success', status=status.HTTP_202_ACCEPTED)



class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = IsStaffOrReadOnly,

    def create(self, request, *args, **kwargs):
        # Добавить валидацию на аутисткий ввод строчки опций
        data = request.data

        serializer = CategorySerializer(data=data)
        # serializer.author_id = request.user.pk
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class TransactionsViewSet(viewsets.ReadOnlyModelViewSet):
    """
    This viewset automatically provides `list` and `detail` actions.
    """
    queryset = Transaction.objects.all().order_by('created_at').reverse()
    serializer_class = TransactionSerializer
    permission_classes = IsAuthenticated,

    def post(self, request, format=None):
        serializer = TransactionSerializer(data=request.data)
        from_user = request.user.pk
        request.data['from_user'] = from_user
        request.data['category'] = 1
        # сделать гет по имени категории

        cat = Category.objects.get(pk=1)
        if str(request.data['amount']) not in (cat.values.split(',')):
            return HttpResponseBadRequest({'Not valid amount of points for this category'})

        if serializer.is_valid():
            to_user = request.data['to_user']
            amount = int(request.data['amount'])
            From_User = get_user_model().objects.get(pk=from_user)
            To_User = get_user_model().objects.get(pk=to_user)
            if int(From_User.share_points) < amount:
                return HttpResponseBadRequest({'Недостаточно средств'})
            To_User.personal_points = str(int(To_User.personal_points) + amount)
            From_User.share_points = str(int(From_User.share_points) - amount)
            To_User.save()
            From_User.save()
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @api_view(['POST'])
    def superpost(request, format=None):
        data = request.data
        data['from_user'] = request.user.pk
        upd_users = data['to_user']

        try:
            cat = Category.objects.get(pk=data['category'])
            print(cat.name)
            if cat.name == "Спасибо":
                return HttpResponseBadRequest({'Category "Спасибо" is not valid for special actions'})
        except:
            return HttpResponseBadRequest({'Category does not exist'})

        if str(data['amount']) not in (cat.values.split(',')):
            return HttpResponseBadRequest({'Not valid amount of points'})

        s_data = []
        for to_user in upd_users:
            data['to_user'] = to_user
            line = data.copy()
            s_data.append(line)

        serializer = TransactionSerializer(data=s_data, many=True)
        if serializer.is_valid():

            users = get_user_model().objects.filter(pk__in=upd_users)
            for to_user in users:
                to_user.personal_points = str(int(to_user.personal_points) + int(data['amount']))
                to_user.save()
            serializer.save()
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        return Response(serializer.data, status=status.HTTP_201_CREATED)


class FeedbackMessageViewSet(viewsets.ModelViewSet):
    queryset = FeedbackMessage.objects.all().order_by('created_at').reverse()
    serializer_class = FeedbackMessageSerializer

    def get_permissions(self):
        if (self.action == 'create'):
            permission_classes = [IsAuthenticated]
        else:
            permission_classes = [IsAdminUser]
        return [permission() for permission in permission_classes]

    def create(self, request, *args, **kwargs):

        data = request.data

        data['author'] = request.user.pk

        serializer = CreateFeedbackMessageSerializer(data=data)
        if serializer.is_valid():
            user = get_user_model().objects.get(pk=data['author'])
            admin = get_user_model().objects.get(pk=1)

            backmessage = user.first_name + ',\n' + \
                          'Мы получили твоё обращение и уже обрабатываем его!\n' \
                          + 'Текст: \n' \
                          + data['text'] + \
                          '\n\nПосле рассмотрения администратор свяжется с тобой  \n\n\n\n' + \
                          'С уважением, \nкоманда Murano Gamification'

            formatopic = data['topic'].replace(' ', "%20")
            adminmessage = 'От: ' + user.first_name + " " + user.last_name + \
                           '\nТема: ' + serializer.validated_data['topic'] + ' \n    ' + \
                           serializer.validated_data['text'] \
                           + ' \n \n \n mailto:' + user.email + '?subject=' + formatopic + '&body=' + user.first_name + ',%20cпасибо%20за%20обращение!'

            connection = mail.get_connection()
            connection.open()

            mailer = 'muranomailer@mail.ru'

            email1 = mail.EmailMessage(
                'Новое обращение',
                adminmessage,
                mailer,
                [admin.email],
            )
            email2 = mail.EmailMessage(
                'Обратная связь с MuranoGamification',
                backmessage,
                mailer,
                [user.email],
            )

            connection.send_messages([email1, email2])
            connection.close()

            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ExcelHandler(viewsets.ViewSet):
    permission_classes = IsAdminUser,
    throttle_classes = OncePerDayUserThrottle,

    def export_xls(self, request, *args, **kwargs):
        user = get_user_model().objects.get(pk=request.user.pk)

        wb = xlwt.Workbook(encoding='utf-8')
        empty = True

        if "Users" in request.data['selected']:
            ws = wb.add_sheet('Users')
            # Sheet header, first row
            row_num = 0
            font_style = xlwt.XFStyle()
            font_style.font.bold = True

            columns = ['Имя', 'Фамилия', 'Email', 'Баллы Спасибо', "Личные Баллы"]
            for col_num in range(len(columns)):
                ws.write(row_num, col_num, columns[col_num], font_style)
            # Sheet body, remaining rows
            font_style = xlwt.XFStyle()
            rows = get_user_model().objects.all().order_by('personal_points').values_list('first_name', 'last_name',
                                                                                          'email', 'share_points',
                                                                                          'personal_points')
            for row in rows:
                row_num += 1
                for col_num in range(len(row)):
                    ws.write(row_num, col_num, row[col_num], font_style)
            empty = False

        if "Transactions" in request.data['selected']:
            ws1 = wb.add_sheet('Транзакции')
            # Sheet header, first row
            row_num = 0
            font_style = xlwt.XFStyle()
            font_style.font.bold = True

            columns = ['От', 'Кому', 'Категроия', 'Количество', "Комментарий", "Дата"]
            for col_num in range(len(columns)):
                ws1.write(row_num, col_num, columns[col_num], font_style)
            # Sheet body, remaining rows
            font_style = xlwt.XFStyle()
            rows = Transaction.objects.all().order_by('created_at').reverse().values_list('from_user_id', 'to_user_id',
                                                                                          'category', 'amount',
                                                                                          'comment', 'created_at')
            for row in rows:
                row_num += 1
                from_user = get_user_model().objects.get(pk=row[0])
                f_fio = from_user.first_name + " " + from_user.last_name
                to_user = get_user_model().objects.get(pk=row[1])
                t_fio = to_user.first_name + " " + to_user.last_name
                cat = Category.objects.get(pk=row[2]).name

                ws1.write(row_num, 0, f_fio, font_style)
                ws1.write(row_num, 1, t_fio, font_style)
                ws1.write(row_num, 2, cat, font_style)
                ws1.write(row_num, 3, row[3], font_style)
                ws1.write(row_num, 4, row[4], font_style)
                ws1.write(row_num, 5, str(row[5]), font_style)
            empty = False

        if empty:
            return Response(data={'error': 'no matching for your keywords'}, status=status.HTTP_400_BAD_REQUEST)

        wb.save('Gamification.xls');

        connection = mail.get_connection()
        connection.open()

        mailer = 'muranomailer@mail.ru'

        email = mail.EmailMessage(
            'Gamification XLS',
            "Вы запросили данные в XLS формате",
            mailer,
            [user.email],
        )

        email.attach_file('Gamification.xls')

        connection.send_messages([email])
        connection.close()

        os.remove('Gamification.xls')

        return Response({'text': "Yass"})


class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = IsStaffOrReadOnly,

    def create(self, request, *args, **kwargs):
        serializer = ProductSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def partial_update(self, request, *args, **kwargs):
        serializer = ProductSerializer(data=request.data, partial=True)
        if serializer.is_valid():
            # instance = Product.objects.get(pk=request.data['id'])
            instance = self.get_object()

            serializer.update(instance, serializer.validated_data)
            print('_+_+_+_+_+_+_+_+_+')
            response = serializer.to_representation(instance)
            return Response(response, status=status.HTTP_202_ACCEPTED)


            if 'image' not in request.data:
                return Response(request.data, status=status.HTTP_202_ACCEPTED)
            else:
                return Response("idk how return form data", status=status.HTTP_202_ACCEPTED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.all().order_by('created_at').reverse()
    serializer_class = OrderSerializer

    def get_permissions(self):
        if (self.action == 'create'):
            permission_classes = [IsAuthenticated]
        else:
            permission_classes = [IsAdminUser]
        return [permission() for permission in permission_classes]

    def create(self, request, *args, **kwargs):
        data = request.data
        data['customer'] = request.user.pk
        serializer = OrderCreateSerializer(data=data)
        if serializer.is_valid():
            order = serializer.save()
            serializer = OrderCreateSerializer(order)
            return Response({'data': 'f'}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def partial_update(self, request, *args, **kwargs):
        data = request.data
        if not data['active']:
            now = timezone.now()
            data['delivered_at'] = now
        else:
            data['delivered_at'] = None

        serializer = OrderStatusSerializer(data=data, partial=True)
        if serializer.is_valid():
            # instance = Product.objects.get(pk=request.data['id'])
            instance = self.get_object()
            serializer.update(instance, serializer.validated_data)
            resp = serializer.data.copy()
            resp['id'] = self.get_object().pk
            return Response(resp, status=status.HTTP_202_ACCEPTED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# class InterestViewSet(viewsets.ModelViewSet):
#     queryset = Interest.objects.all().order_by('created_at').reverse()
#     serializer_class = InterestSerializer


def start(request):
    return render(request, 'dist/index.html')
