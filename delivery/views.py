from datetime import datetime 
from django.utils import timezone
from django.shortcuts import redirect, render
from farmfills_admin.business import daily_delivery_query
from users.models import Staff, User, ExtraLess, Vacation, Subscription, Delivery, RouteAssign, Route, Product
from users.views import get_client_ip, getQuantityOfDate, getEndBalanceOfMonth, last_day_of_month, format_number
from django.db import IntegrityError
from django.db.models import Q, Sum
import pytz
from .models import DeliveryData


# login page
def login(request):
    user_id = None
    try:
        user_id = request.session['farmfills_staff_id']
    except:
        pass
    error = request.GET.get('error', None)
    if Staff.objects.filter(id= user_id, delivery=True).exists():
        return redirect('delivery_notification')
    return render(request, 'delivery_login.html', {'error':error})


# delivery list page
def delivery(request):
    user_id = None
    try:
        user_id = request.session['farmfills_staff_id']
    except:
        pass
    if Staff.objects.filter(id= user_id, delivery=True).exists():

        # check if the delivery boy is early
        early = False
        right_time = timezone.localtime().replace(hour=2, minute=1, second=0, microsecond=0)
        if right_time > timezone.localtime():  # early if it's < 2:01 am
            early = True
        
        # get the generated delivery list
        staff = Staff.objects.get(id= user_id, delivery=True)
        deliveryList = get_today_delivery_list(staff.route.id)
        
        # check if the delivery boy already started delivery
        deliveryData = None
        try:
            deliveryData = Delivery.objects.get(delivery_boy=staff, date=timezone.localdate())
            if deliveryData.start_time is None: deliveryData = None
        except:
            pass

        return render(request, 'delivery_delivery.html', {
            'deliveryList': deliveryList['list'], 
            'assignedList': deliveryList['assigned'], 
            'total': deliveryList['total'], 
            'date': timezone.localdate(),
            'deliveryData': deliveryData, 
            'early': early
        })
    else:
        return redirect('delivery_login')

def get_today_delivery_list(route_id):
    output = {'list': [], 'total': 0, 'assigned': []}
    result = daily_delivery_query(None, route_id)

    for row in result:
        (_, delivery_name, _, _, _, _, _, _, assigned, total_quantity, _) = row
        if assigned:
            output['assigned'].append({'name': delivery_name, 'packet': int(total_quantity)})
        else:
            output['list'].append({'name': delivery_name, 'packet': int(total_quantity)})
        output['total'] += int(total_quantity)

    return output


# notification page
def notification(request):
    user_id = None
    try:
        user_id = request.session['farmfills_staff_id']
    except:
        pass
    error = request.GET.get('error', None)
    if Staff.objects.filter(id= user_id, delivery=True).exists():
        early = False
        right_time = timezone.localtime(timezone.now()).replace(hour=2, minute=0, second=0, microsecond=0)
        if right_time > timezone.localtime(timezone.now()):
            early = True
        staff = Staff.objects.get(id= user_id, delivery=True)
        
        notifications = getNotifications(staff.route)

        return render(request, 'delivery_notification.html', {
            'new_sub':notifications['new_sub'], 
            'new_vacation':notifications['new_vacation'], 
            'ended_vacation':notifications['ended_vacation'], 
            'extra':notifications['extra'],
            'early':early
            })
    else:
        return redirect('delivery_login')


# allowance page
def allowance(request):
    user_id = None
    try:
        user_id = request.session['farmfills_staff_id']
    except:
        pass
    error = request.GET.get('error', None)
    date = request.GET.get('date', None)
    if Staff.objects.filter(id= user_id, delivery=True).exists():
        staff = Staff.objects.get(id= user_id, delivery=True)
        if date is None:
            date = timezone.localtime(timezone.now()).date()
        else:
            date = datetime.fromtimestamp(int(date)).date()
        allowanceData = getAllowanceData(staff, date)

        return render(request, 'delivery_allowance.html', {'error':error, 'allowanceData':allowanceData})
    else:
        return redirect('delivery_login')


# formating date for matching month and year only
def trunc_date(someDate):
    return someDate.replace(day=1)


# get delivery allowance data of any month of any staff
def getAllowanceData(staff, date):
    date = trunc_date(date)
    data = Delivery.objects.filter(delivery_boy=staff).order_by('-date')

    output = {'date':date.strftime("%b %Y"), 'total':0, 'list':[]}

    for d in data:
        if trunc_date(d.date) == date:
            
            d_allowance = float(d.packets * 2)

            if d.packets_variation is not None:
                d_allowance = float((d.packets + d.packets_variation) * 2)
            
            f_allowance_per_km = 2.5

            if staff.vehicle == 'scooter':
                f_allowance_per_km = 3

            f_allowance = float(d.km) * f_allowance_per_km  

            if d.km_variation is not None:
                f_allowance = float((d.km + d.km_variation) )* f_allowance_per_km
            
            
            total = round(d_allowance + f_allowance)

            output['total'] += total

            output['list'].append({'date':d.date.strftime("%b %d"), 'packets':d.packets, 'distance':d.km, 'delivery_allowance':d_allowance, 'fuel_allowance':f_allowance, 'total':total})

    return output


# get delivery list of a specific route
def getDeliveryList(route):

    customers = User.objects.filter(route=route).order_by('route_order')

    thisdate = timezone.localtime(timezone.now()).date()
    output  = {'date': thisdate.strftime("%b %d, %Y"), 'total':0, 'list':[], 'assigned':[]}

    product = Product.objects.get(id=1)

    for c in customers:

        try:
            assign = RouteAssign.objects.get(user=c)
            if assign.to_route !=  route:
                continue
        except:
            pass

        last_day = last_day_of_month(timezone.localtime(timezone.now()))
        balance = getEndBalanceOfMonth(last_day, c)

        if c.user_type.suspend:
            if format_number(balance) <= 0:
                continue

        extraless = ExtraLess.objects.filter(user=c)
        vacations = Vacation.objects.filter(user=c)
        subs = Subscription.objects.filter(user=c)

        in_vacation = False

        for e in extraless:
            if e.start_date <= thisdate and e.end_date is None:
                if c.user_type.suspend:
                    if e.quantity * (product.price + c.user_type.price_variation) > balance:
                        in_vacation = True
                        break

                output['total'] += int(e.quantity * 2)
                output['list'].append({'user':c, 'packet': int(e.quantity * 2)})
                in_vacation = True
                break
            elif e.end_date is not None:
                if e.start_date <= thisdate and e.end_date >= thisdate:
                    if c.user_type.suspend:
                        if e.quantity * (product.price + c.user_type.price_variation) > balance:
                            in_vacation = True
                            break

                    output['total'] += int(e.quantity * 2)
                    output['list'].append({'user':c, 'packet': int(e.quantity * 2)})
                    
                    in_vacation = True
                    break
        
        if not in_vacation:
            for v in vacations:

                if v.start_date <= thisdate and v.end_date is None :
                    output['list'].append({'user':c, 'packet': 0})
                    in_vacation = True
                    break
                elif v.end_date is not None:
                    if v.start_date <= thisdate and v.end_date >= thisdate:
                        output['list'].append({'user':c, 'packet': 0})
                        in_vacation = True
                        break
        
        if not in_vacation:
            for s in subs:

                if s.start_date <= thisdate and s.end_date is None :
                    packet =  0
                    try:
                        packet = int(getQuantityOfDate(s, timezone.localtime(timezone.now()).date()) * 2)
                    except:
                        pass
                    if c.user_type.suspend:
                        if float(packet/2) * float(product.price + c.user_type.price_variation) > balance:
                            in_vacation = True
                            break
                            
                    output['total'] += packet
                    output['list'].append({'user':c, 'packet': int(packet)})
                    break
                elif s.end_date is not None:
                    if s.start_date <= thisdate and s.end_date >= thisdate:
                        packet =  0
                        try:
                            packet = int(getQuantityOfDate(s, timezone.localtime(timezone.now()).date()) * 2)
                        except:
                            pass
                        if c.user_type.suspend:
                            if float(packet/2) * float(product.price + c.user_type.price_variation) > balance:
                                in_vacation = True
                                break
                                
                        output['total'] += packet
                        output['list'].append({'user':c, 'packet': int(packet)})
                        break
        

    assigned = RouteAssign.objects.filter(to_route=route)
    for a in assigned:

        last_day = last_day_of_month(timezone.localtime(timezone.now()))
        balance = getEndBalanceOfMonth(last_day, a.user)

        if a.user.user_type.suspend:
            if format_number(balance) <= 0:
                continue

        extraless = ExtraLess.objects.filter(user=a.user)
        vacations = Vacation.objects.filter(user=a.user)
        subs = Subscription.objects.filter(user=a.user)

        in_vacation = False

        for e in extraless:
            if e.start_date <= thisdate and e.end_date is None:
                if a.user.user_type.suspend:
                    if e.quantity * (product.price + ca.user.user_type.price_variation) > balance:
                        in_vacation = True
                        break

                output['total'] += int(e.quantity * 2)
                output['assigned'].append({'user':a.user, 'packet': int(e.quantity * 2)})
                in_vacation = True
                break
            elif e.end_date is not None:
                if e.start_date <= thisdate and e.end_date >= thisdate:
                    if a.user.user_type.suspend:
                        if e.quantity * (product.price + a.user.user_type.price_variation) > balance:
                            in_vacation = True
                            break

                    output['total'] += int(e.quantity * 2)
                    output['assigned'].append({'user':a.user, 'packet': int(e.quantity * 2)})
                    
                    in_vacation = True
                    break
        
        if not in_vacation:
            for v in vacations:

                if v.start_date <= thisdate and v.end_date is None :
                    output['assigned'].append({'user':a.user, 'packet': 0})
                    in_vacation = True
                elif v.end_date is not None:
                    if v.start_date <= thisdate and v.end_date >= thisdate:
                        output['assigned'].append({'user':a.user, 'packet': 0})
                        in_vacation = True
        
        if not in_vacation:
            for s in subs:

                if s.start_date <= thisdate and s.end_date is None :
                    packet =  0
                    try:
                        packet = int(getQuantityOfDate(s, timezone.localtime(timezone.now()).date()) * 2)
                    except:
                        pass
                    if a.user.user_type.suspend:
                        if float(packet/2) * float(product.price + a.user.user_type.price_variation) > balance:
                            in_vacation = True
                            break
                    output['total'] += packet
                    output['assigned'].append({'user':a.user, 'packet': int(packet)})
                elif s.end_date is not None:
                    if s.start_date <= thisdate and s.end_date >= thisdate:
                        packet =  0
                        try:
                            packet = int(getQuantityOfDate(s, timezone.localtime(timezone.now()).date()) * 2)
                        except:
                            pass
                        if a.user.user_type.suspend:
                            if float(packet/2) * float(product.price + a.user.user_type.price_variation) > balance:
                                in_vacation = True
                                break
                        output['total'] += packet
                        output['assigned'].append({'user':a.user, 'packet': int(packet)})

    return output



# get delivery list of a specific route within a specific day
def getDeliveryListByDate(route, date):
    
    customers = User.objects.filter(route=route).order_by('route_order')

    thisdate = datetime.strptime(date, '%Y-%m-%d').replace(tzinfo=pytz.UTC).date()
    output  = {'date': thisdate.strftime("%b %d, %Y"), 'total':0, 'list':[], 'assigned':[]}

    product = Product.objects.get(id=1)

    for c in customers:

        try:
            assign = RouteAssign.objects.get(user=c)
            if assign.to_route !=  route:
                continue
        except:
            pass

        last_day = last_day_of_month(datetime.strptime(date, '%Y-%m-%d').replace(tzinfo=pytz.UTC))
        balance = getEndBalanceOfMonth(last_day, c)

        if c.user_type.suspend:
            if format_number(balance) <= 0:
                continue

        extraless = ExtraLess.objects.filter(user=c)
        vacations = Vacation.objects.filter(user=c)
        subs = Subscription.objects.filter(user=c)

        in_vacation = False

        for e in extraless:
            if e.start_date <= thisdate and e.end_date is None:
                if c.user_type.suspend:
                    if e.quantity * (product.price + c.user_type.price_variation) > balance:
                        in_vacation = True
                        break

                output['total'] += int(e.quantity * 2)
                output['list'].append({'user':c, 'packet': int(e.quantity * 2)})
                in_vacation = True
                break
            elif e.end_date is not None:
                if e.start_date <= thisdate and e.end_date >= thisdate:
                    if c.user_type.suspend:
                        if e.quantity * (product.price + c.user_type.price_variation) > balance:
                            in_vacation = True
                            break

                    output['total'] += int(e.quantity * 2)
                    output['list'].append({'user':c, 'packet': int(e.quantity * 2)})
                    
                    in_vacation = True
                    break
        
        if not in_vacation:
            for v in vacations:

                if v.start_date <= thisdate and v.end_date is None :
                    output['list'].append({'user':c, 'packet': 0})
                    in_vacation = True
                    break
                elif v.end_date is not None:
                    if v.start_date <= thisdate and v.end_date >= thisdate:
                        output['list'].append({'user':c, 'packet': 0})
                        in_vacation = True
                        break
        
        if not in_vacation:
            for s in subs:

                if s.start_date <= thisdate and s.end_date is None :
                    packet =  0
                    try:
                        packet = int(getQuantityOfDate(s, thisdate) * 2)
                    except:
                        pass
                    if c.user_type.suspend:
                        if float(packet/2) * float(product.price + c.user_type.price_variation) > balance:
                            in_vacation = True
                            break
                            
                    output['total'] += packet
                    output['list'].append({'user':c, 'packet': int(packet)})
                    break
                elif s.end_date is not None:
                    if s.start_date <= thisdate and s.end_date >= thisdate:
                        packet =  0
                        try:
                            packet = int(getQuantityOfDate(s, thisdate) * 2)
                        except:
                            pass
                        if c.user_type.suspend:
                            if float(packet/2) * float(product.price + c.user_type.price_variation) > balance:
                                in_vacation = True
                                break
                                
                        output['total'] += packet
                        output['list'].append({'user':c, 'packet': int(packet)})
                        break
        

    assigned = RouteAssign.objects.filter(to_route=route)
    for a in assigned:

        last_day = last_day_of_month(datetime.strptime(date, '%Y-%m-%d').replace(tzinfo=pytz.UTC))
        balance = getEndBalanceOfMonth(last_day, a.user)

        if a.user.user_type.suspend:
            if format_number(balance) <= 0:
                continue

        extraless = ExtraLess.objects.filter(user=a.user)
        vacations = Vacation.objects.filter(user=a.user)
        subs = Subscription.objects.filter(user=a.user)

        in_vacation = False

        for e in extraless:
            if e.start_date <= thisdate and e.end_date is None:
                if a.user.user_type.suspend:
                    if e.quantity * (product.price + ca.user.user_type.price_variation) > balance:
                        in_vacation = True
                        break

                output['total'] += int(e.quantity * 2)
                output['assigned'].append({'user':a.user, 'packet': int(e.quantity * 2)})
                in_vacation = True
                break
            elif e.end_date is not None:
                if e.start_date <= thisdate and e.end_date >= thisdate:
                    if a.user.user_type.suspend:
                        if e.quantity * (product.price + a.user.user_type.price_variation) > balance:
                            in_vacation = True
                            break

                    output['total'] += int(e.quantity * 2)
                    output['assigned'].append({'user':a.user, 'packet': int(e.quantity * 2)})
                    
                    in_vacation = True
                    break
        
        if not in_vacation:
            for v in vacations:

                if v.start_date <= thisdate and v.end_date is None :
                    output['assigned'].append({'user':a.user, 'packet': 0})
                    in_vacation = True
                elif v.end_date is not None:
                    if v.start_date <= thisdate and v.end_date >= thisdate:
                        output['assigned'].append({'user':a.user, 'packet': 0})
                        in_vacation = True
        
        if not in_vacation:
            for s in subs:

                if s.start_date <= thisdate and s.end_date is None :
                    packet =  0
                    try:
                        packet = int(getQuantityOfDate(s, thisdate) * 2)
                    except:
                        pass
                    if a.user.user_type.suspend:
                        if float(packet/2) * float(product.price + a.user.user_type.price_variation) > balance:
                            in_vacation = True
                            break
                    output['total'] += packet
                    output['assigned'].append({'user':a.user, 'packet': int(packet)})
                elif s.end_date is not None:
                    if s.start_date <= thisdate and s.end_date >= thisdate:
                        packet =  0
                        try:
                            packet = int(getQuantityOfDate(s, thisdate) * 2)
                        except:
                            pass
                        if a.user.user_type.suspend:
                            if float(packet/2) * float(product.price + a.user.user_type.price_variation) > balance:
                                in_vacation = True
                                break
                        output['total'] += packet
                        output['assigned'].append({'user':a.user, 'packet': int(packet)})

    return output


# get notifications   
def getNotifications(route):
    customers = User.objects.filter(route=route).order_by('route_order')

    thisdate = timezone.localtime(timezone.now()).date()
    output  = {'new_sub':[], 'new_vacation':[], 'extra':[], 'ended_vacation':[]}

    for c in customers:
        extraless = ExtraLess.objects.filter(user=c)
        vacations = Vacation.objects.filter(user=c)
        subs = Subscription.objects.filter(user=c)

        in_vacation = False

        for e in extraless:
            if e.start_date <= thisdate and e.end_date is None:
                output['extra'].append({'user':c, 'packet': int(e.quantity * 2)})
                in_vacation = True
            elif e.end_date is not None:
                if e.start_date <= thisdate and e.end_date >= thisdate :
                    output['extra'].append({'user':c, 'packet': int(e.quantity * 2)})
                    in_vacation = True
        
        if not in_vacation:
            for v in vacations:

                if v.start_date == thisdate:
                    output['new_vacation'].append({'user':c})
                    in_vacation = True
                elif v.end_date == thisdate:
                    output['ended_vacation'].append({'user':c})
                    in_vacation = True
        
        if not in_vacation:
            for s in subs:
                if s.start_date == thisdate:
                    packet =  int(getQuantityOfDate(s, timezone.localtime(timezone.now()).date()) * 2)
                    output['new_sub'].append({'user':c, 'packet': packet, 'type':s.sub_type})
        
    return output


# login validation
def login_validation(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        try:
            staff = Staff.objects.get(uname=username, password=password, delivery=True)
            ip = get_client_ip(request)
            Staff.objects.filter(ip=ip).update(ip='')
            staff.ip = ip
            staff.save()
            request.session['farmfills_staff_id'] = staff.id
            return redirect('delivery_notification')
        except:
            return redirect('/delivery/login?error=Username or password is invalid')



# start delivery
def start_delivery(request):
    user_id = None
    try:
        user_id = request.session['farmfills_staff_id']
    except:
        pass
    if Staff.objects.filter(id= user_id, delivery=True).exists():
        staff = Staff.objects.get(id= user_id, delivery=True)
        if request.method == 'POST':
            packets = request.POST.get('packets')
            try:
                delivery = Delivery.objects.get(delivery_boy=staff, date=timezone.localtime(timezone.now()).date())
                delivery.start_time = timezone.localtime(timezone.now()).time()
                delivery.save()
                return redirect('delivery_list')
            except Delivery.DoesNotExist:
                try:
                    delivery = Delivery(date=timezone.localtime(timezone.now()).date(), start_time=timezone.localtime(timezone.now()).time(), route=staff.route, packets=packets, delivery_boy=staff, km=staff.km)
                    delivery.save()
                except IntegrityError:
                    # a second tap already created today's delivery
                    pass
                return redirect('delivery_list')
        else:
            return redirect('delivery_list')
    else:
        return redirect('delivery_login')


# end delivery
def end_delivery(request):
    user_id = None
    try:
        user_id = request.session['farmfills_staff_id']
    except:
        pass
    if Staff.objects.filter(id= user_id, delivery=True).exists():
        staff = Staff.objects.get(id= user_id, delivery=True)
        if request.method == 'POST':
            delivery = Delivery.objects.get(delivery_boy=staff, date=timezone.localtime(timezone.now()).date())
            delivery.end_time = timezone.localtime(timezone.now()).time()
            delivery.save()
            return redirect('delivery_list')
        else:
            return redirect('delivery_list') 
    else:
        return redirect('delivery_login')   
